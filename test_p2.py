"""Test P2: Verify find_company_website rejects wrong matches."""
from scraper import find_company_website

test_cases = [
    ("The AI Signal", "AI Engineer Internship startup OR careers"),
    ("Fortune Analytics", "AI Engineer Internship startup OR careers"),
    ("Abstrabit Technologies", "AI Engineer Internship startup OR careers"),
    ("Pathnovo Solutions", "AI Engineer Internship startup OR careers"),
]

for company, hint in test_cases:
    website = find_company_website(company, search_hint=hint)
    status = website if website else "Not found (correctly rejected)"
    print(f"{company}: {status}")
