"""
Unstop scraper, founder discovery, and company email discovery module.
Fetches public internship listings for a given target field / keyword.
Performs clean HTML parsing of job descriptions, best-effort founder lookups,
and automated company email extraction from company websites.
"""

import re
import html
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json,*/*",
}

# Common generic/spam emails to filter out
IGNORE_EMAIL_PATTERNS = {
    "noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster",
    "example.com", "sentry.io", "gravatar.com", "schema.org",
    "wixpress.com", "googleapis.com", "w3.org",
}


def clean_html_text(raw_html: str) -> str:
    """Convert HTML snippet to clean, readable plain text."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator=" \n ", strip=True)
    text = html.unescape(text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _is_valid_company_email(email: str) -> bool:
    """Filter out generic/useless email addresses."""
    email_lower = email.lower()
    for pattern in IGNORE_EMAIL_PATTERNS:
        if pattern in email_lower:
            return False
    # Must look like a real email
    if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$", email):
        return False
    # Skip common freemail providers (we want company domain emails)
    freemail = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "protonmail.com"}
    domain = email.split("@")[1].lower()
    if domain in freemail:
        return False
    return True


def find_company_website(company_name: str, search_hint: str = "") -> str:
    """
    Search Bing for the company's official website using cite tag extraction.
    Verifies the candidate URL actually mentions the company name before accepting it.
    Returns the URL or empty string. Never fails the pipeline.
    """
    if not company_name or company_name.lower() in ["company", "confidential", "stealth"]:
        return ""

    skip_domains = [
        "linkedin.com", "facebook.com", "twitter.com", "instagram.com",
        "unstop.com", "youtube.com", "glassdoor.com", "ambitionbox.com",
        "wikipedia.org", "crunchbase.com", "bing.com", "microsoft.com",
        "merriam-webster.com", "dictionary.cambridge.org", "wiktionary.org",
    ]

    # Build a core name for verification (strip generic suffixes)
    core_name = re.sub(r'(?i)\b(pvt|ltd|inc|llc|corp|technologies|solutions|group|private|limited)\b', '', company_name).strip().lower()
    core_name = re.sub(r'[^a-z0-9 ]+', '', core_name).strip()

    try:
        query = f'"{company_name}" {search_hint}'.strip()
        url = f"https://www.bing.com/search?q={requests.utils.quote(query)}"
        resp = requests.get(url, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            results = soup.find_all("li", class_="b_algo")
            for r in results[:5]:
                cite = r.find("cite")
                if cite:
                    cite_text = cite.get_text().strip()
                    if not cite_text.startswith("http"):
                        cite_text = "https://" + cite_text
                    parsed = urlparse(cite_text)
                    if parsed.hostname and not any(sd in parsed.hostname for sd in skip_domains):
                        candidate_url = f"{parsed.scheme}://{parsed.hostname}"
                        
                        # Verify: fetch the homepage and check if the company name appears
                        if core_name:
                            try:
                                verify_resp = requests.get(candidate_url, headers=HEADERS, timeout=6, allow_redirects=True)
                                if verify_resp.status_code == 200:
                                    page_text = verify_resp.text.lower()
                                    if core_name in page_text:
                                        return candidate_url
                                    else:
                                        print(f"      [!] Website verification failed: {candidate_url} does not mention '{core_name}'. Trying next result...")
                                        continue
                            except Exception:
                                continue
                        else:
                            return candidate_url
    except Exception:
        pass
    return ""


def find_company_email(company_name: str, company_website: str = "") -> str:
    """
    Discover a contact email for the company by:
    1. Scraping their website's contact/about/careers pages for mailto: links and email patterns.
    2. Falls back gracefully if nothing found.
    Never fails the pipeline.
    """
    if not company_website:
        company_website = find_company_website(company_name)
    if not company_website:
        return ""

    # Pages likely to contain contact emails
    candidate_paths = ["/", "/contact", "/contact-us", "/about", "/about-us", "/careers", "/team"]
    found_emails = set()

    for path in candidate_paths:
        try:
            page_url = urljoin(company_website, path)
            resp = requests.get(page_url, headers=HEADERS, timeout=6, allow_redirects=True)
            if resp.status_code != 200:
                continue

            page_text = resp.text

            # Strategy 1: Find mailto: links
            soup = BeautifulSoup(page_text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    if _is_valid_company_email(email):
                        found_emails.add(email)

            # Strategy 2: Regex scan the raw HTML for email patterns
            raw_emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", page_text)
            for em in raw_emails:
                if _is_valid_company_email(em):
                    found_emails.add(em)

            # If we found anything on this page, no need to check more pages
            if found_emails:
                break

        except Exception:
            continue

    if not found_emails:
        return ""

    # Prioritize: hr@ > careers@ > contact@ > info@ > hello@ > any other
    priority_prefixes = ["hr", "careers", "career", "hiring", "recruit", "contact", "info", "hello"]
    for prefix in priority_prefixes:
        for em in found_emails:
            if em.lower().startswith(prefix + "@"):
                return em

    return found_emails.pop()


def extract_company_context(company_website: str, company_name: str = "") -> str:
    """Extract text from homepage and /about to give the LLM context on what the company does."""
    if not company_website:
        return ""
    
    context = ""
    candidate_paths = ["/", "/about", "/about-us"]
    for path in candidate_paths:
        try:
            page_url = urljoin(company_website, path)
            resp = requests.get(page_url, headers=HEADERS, timeout=6, allow_redirects=True)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                # Remove scripts, styles, and boilerplate navigation
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()
                text = soup.get_text(separator=" ", strip=True)
                context += f"\n--- Page: {path} ---\n{text[:1000]}"
                if len(context) > 2000:
                    break
        except Exception:
            continue
            
    # FIX B: Sanity check to verify scraped text actually mentions the company
    if company_name and context:
        import re
        # Strip common generic suffixes to get the core company name
        core_name = re.sub(r'(?i)\b(pvt|ltd|inc|llc|corp|technologies|solutions|group|private|limited)\b', '', company_name).strip().lower()
        core_name = re.sub(r'[^a-z0-9 ]+', '', core_name).strip()
        
        # If the core name isn't found in the text, it's highly likely a mismatched website (e.g. Fortune Magazine instead of Fortune Analytics)
        if core_name and core_name not in context.lower():
            print(f"      [!] Context verification failed for {company_website}: '{core_name}' not mentioned in text.")
            return ""
            
    return context.strip()


def scrape_unstop_internships(target_field: str, limit: int = 10) -> list:
    """
    Query Unstop public internship search for the target field/keywords.
    Returns a list of dicts with job info, founder info, and discovered company email.
    """
    primary_term = target_field.split(",")[0].strip() if target_field else "AI Engineer"

    encoded_term = requests.utils.quote(primary_term)
    url = f"https://unstop.com/api/public/opportunity/search-result?opportunity=internships&searchTerm={encoded_term}&page=1&per_page={limit}"

    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()

    data = response.json()
    items = data.get("data", {}).get("data", [])

    results = []
    for item in items[:limit]:
        job_id = item.get("id")
        title = item.get("title", "Internship")
        company = item.get("organisation", {}).get("name", "Company")
        public_url = item.get("public_url") or item.get("seo_url") or f"o/{job_id}"
        if not public_url.startswith("http"):
            job_url = f"https://unstop.com/{public_url}"
        else:
            job_url = public_url

        raw_details = item.get("details", "")
        clean_jd = clean_html_text(raw_details)

        skills_raw = item.get("required_skills", [])
        skills = [s.get("skill", "") for s in skills_raw if isinstance(s, dict) and s.get("skill")]

        if skills:
            skills_str = ", ".join(skills)
            clean_jd = f"{clean_jd}\n\nRequired Skills: {skills_str}"

        # Discover founder info
        founder_info = find_founder_info(company)

        # Discover company website and email
        search_hint = f"{title} startup OR careers"
        company_website = find_company_website(company, search_hint=search_hint)
        company_email = find_company_email(company, company_website)
        company_context = extract_company_context(company_website, company_name=company)

        print(f"      Company: {company} | Website: {company_website or 'Not found'} | Email: {company_email or 'Not found'}")

        results.append({
            "job_title": title,
            "company": company,
            "job_url": job_url,
            "jd_text": clean_jd,
            "required_skills": skills,
            "founder_name": founder_info["founder_name"],
            "founder_linkedin": founder_info["founder_linkedin"],
            "company_email": company_email,
            "company_context": company_context
        })

    return results


def find_founder_info(company_name: str) -> dict:
    """
    Best effort search for founder name & LinkedIn from public web search.
    Never fails the run if not found.
    """
    result = {"founder_name": "", "founder_linkedin": ""}
    if not company_name or company_name.lower() in ["company", "confidential", "stealth"]:
        return result

    try:
        query = f"{company_name} founder CEO linkedin"
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        resp = requests.get(url, headers=HEADERS, timeout=6)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "linkedin.com/in/" in href:
                    match = re.search(r"https%3A%2F%2F[^\&]+", href)
                    if match:
                        result["founder_linkedin"] = requests.utils.unquote(match.group(0))
                    elif href.startswith("http"):
                        result["founder_linkedin"] = href
                    break
    except Exception:
        pass

    return result


if __name__ == "__main__":
    import sys
    field = sys.argv[1] if len(sys.argv) > 1 else "AI Engineer"
    print(f"Scraping for: {field}...")
    jobs = scrape_unstop_internships(field, limit=2)
    print(f"\nSuccessfully scraped {len(jobs)} jobs:")
    for j in jobs:
        print(f"- {j['job_title']} at {j['company']} ({j['job_url']})")
        print(f"  Email: {j['company_email'] or 'Not found'}")
        print(f"  JD Preview: {j['jd_text'][:120]}...\n")
