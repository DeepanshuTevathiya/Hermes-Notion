"""
Hermes-Notion Pipeline: scan_and_draft.py
Triggered via GitHub Actions cron (or manual trigger).

Workflow:
1. Fetch candidate profile and resume (strictly into memory from Notion).
2. Scrape latest public internships from Unstop matching target field.
3. For each found opportunity (capped at 3 per run):
   a. Compute ATS Score (0-100) & isolate missing skills/gaps.
   b. Generate truthful tailored resume in-memory (no hallucinations).
   c. Best-effort founder discovery.
   d. Draft personalized cold outreach email.
   e. Save structured record in Notion Opportunities with Status="Pending Approval".
4. Write structured execution summary to Notion Run Log with real timestamps.
"""

import sys
from datetime import datetime, timezone
from config import get_config
from notion_ops import (
    get_notion_client,
    read_profile,
    write_opportunity,
    write_run_log,
    _query_database,
)
from scraper import scrape_unstop_internships
from llm_pipeline import (
    get_groq_client,
    score_and_identify_gaps,
    tailor_resume_safely,
    draft_outreach_email,
)


def get_existing_job_links(client, opportunities_db_id: str) -> set:
    """Retrieve existing opportunity links from Notion to avoid duplicate postings."""
    try:
        pages = _query_database(client, opportunities_db_id, page_size=100)
        links = set()
        for page in pages:
            link = page.get("properties", {}).get("Job Link", {}).get("url")
            if link:
                links.add(link.strip())
        return links
    except Exception as e:
        print(f"[Warning] Failed to fetch existing links: {e}")
        return set()


def run_pipeline(trigger_type: str = "Cron"):
    print(f"=== Starting Hermes-Notion scan_and_draft ({trigger_type}) ===")
    cfg = get_config()
    notion = get_notion_client(cfg["NOTION_TOKEN"])
    groq = get_groq_client(cfg["GROQ_API_KEY"])

    errors = []
    jobs_processed = 0
    opportunities_added = 0

    try:
        # Step 1: Read profile dynamically into memory
        print("[1/4] Reading profile from Notion...")
        profile = read_profile(notion, cfg["NOTION_PROFILE_DB_ID"])
        resume_text = profile.get("resume_text", "")
        candidate_name = profile.get("name", "Candidate")
        target_field = profile.get("target_field") or cfg.get("TARGET_FIELD", "AI Engineer")

        if not resume_text:
            raise ValueError("No resume text found in Notion Profile row.")

        print(f"      Candidate: {candidate_name} | Target: {target_field}")

        # Step 2: Query Unstop for matching internships
        print(f"[2/4] Scraping Unstop for '{target_field}' (limit: 3)...")
        scraped_jobs = scrape_unstop_internships(target_field, limit=3)
        jobs_found = len(scraped_jobs)
        print(f"      Scraped {jobs_found} opportunities from Unstop.")

        if not scraped_jobs:
            print("      No matching jobs found on Unstop.")
            write_run_log(
                notion,
                cfg["NOTION_RUN_LOG_DB_ID"],
                {
                    "trigger_type": trigger_type,
                    "jobs_found": 0,
                    "action_taken": "No new opportunities found on Unstop for target query.",
                    "status": "Success",
                    "error_details": "",
                },
            )
            return

        # Fetch existing links to prevent duplicates
        existing_links = get_existing_job_links(notion, cfg["NOTION_OPPORTUNITIES_DB_ID"])

        # Step 3: Process each opportunity
        print("[3/4] Analyzing jobs with Groq and saving to Notion...")
        for i, job in enumerate(scraped_jobs, start=1):
            job_url = job.get("job_url", "")
            title = job.get("job_title", "Unknown Role")
            company = job.get("company", "Unknown Company")

            if job_url and job_url in existing_links:
                print(f"      [{i}/{jobs_found}] Skipping already existing job: {title} @ {company}")
                continue

            try:
                print(f"      [{i}/{jobs_found}] Processing: {title} @ {company}...")
                jd_text = job.get("jd_text", "")

                # 3a: ATS Scoring and Honest Gap Detection
                eval_res = score_and_identify_gaps(groq, resume_text, jd_text)
                ats_score = eval_res.get("ats_score", 50)
                jd_summary = eval_res.get("jd_summary", "")
                matching_skills = eval_res.get("matching_skills", [])
                missing_skills = eval_res.get("missing_skills", [])

                # 3b: Truthful Resume Tailoring (strictly in-memory)
                tailored_resume = tailor_resume_safely(
                    groq, resume_text, jd_text, matching_skills, missing_skills
                )

                # 3c: Outreach Email Generation
                founder_name = job.get("founder_name", "")
                draft_email = draft_outreach_email(
                    groq,
                    candidate_name,
                    company,
                    title,
                    founder_name,
                    matching_skills,
                    resume_text,
                )

                # 3d: Write to Notion Opportunities DB
                opp_data = {
                    "job_title": title,
                    "company": company,
                    "job_url": job_url,
                    "ats_score": ats_score,
                    "jd_summary": jd_summary,
                    "tailored_resume": tailored_resume,
                    "founder_name": founder_name,
                    "founder_linkedin": job.get("founder_linkedin", ""),
                    "draft_email": draft_email,
                    "company_email": job.get("company_email", ""),
                }
                page_id = write_opportunity(notion, cfg["NOTION_OPPORTUNITIES_DB_ID"], opp_data)
                print(f"          -> Logged to Notion (Page ID: {page_id}) with ATS Score: {ats_score}/100")
                
                opportunities_added += 1
                jobs_processed += 1
                existing_links.add(job_url)

            except Exception as e:
                err_msg = f"Failed on '{title}' @ '{company}': {str(e)}"
                print(f"          [Error] {err_msg}")
                errors.append(err_msg)

        # Step 4: Record Run Log
        print("[4/4] Writing Run Log...")
        status = "Success"
        if errors:
            status = "Partial" if opportunities_added > 0 else "Failed"

        action_summary = f"Scanned {jobs_found} jobs. Added {opportunities_added} new opportunities for human review."
        error_summary = "\n".join(errors) if errors else ""

        write_run_log(
            notion,
            cfg["NOTION_RUN_LOG_DB_ID"],
            {
                "trigger_type": trigger_type,
                "jobs_found": jobs_found,
                "action_taken": action_summary,
                "status": status,
                "error_details": error_summary,
            },
        )
        print(f"=== Scan and Draft Finished with status: {status} ===")

    except Exception as e:
        err_msg = f"Fatal pipeline error: {str(e)}"
        print(f"[FATAL ERROR] {err_msg}")
        try:
            write_run_log(
                notion,
                cfg["NOTION_RUN_LOG_DB_ID"],
                {
                    "trigger_type": trigger_type,
                    "jobs_found": jobs_processed,
                    "action_taken": "Pipeline encountered a fatal crash before completion.",
                    "status": "Failed",
                    "error_details": err_msg,
                },
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    trigger = sys.argv[1] if len(sys.argv) > 1 else "Manual"
    run_pipeline(trigger_type=trigger)
