"""
Phase 1 Verification Script — Notion Connectivity Test.
Tests: read Profile, write Opportunities, write Run Log.
Run locally only. Does NOT commit any personal data.
"""

from config import get_config
from notion_ops import (
    get_notion_client,
    read_profile,
    write_opportunity,
    write_run_log,
)


def main():
    cfg = get_config()
    client = get_notion_client(cfg["NOTION_TOKEN"])
    all_passed = True

    # --- Test 1: Read Profile ---
    print("=" * 50)
    print("TEST 1: Reading Profile database...")
    try:
        profile = read_profile(client, cfg["NOTION_PROFILE_DB_ID"])
        # Print only metadata, never the actual resume content
        print(f"  Name found: {bool(profile['name'])} (length: {len(profile['name'])})")
        print(f"  Resume Text found: {bool(profile['resume_text'])} (length: {len(profile['resume_text'])})")
        print(f"  Additional Info found: {bool(profile['additional_info'])} (length: {len(profile['additional_info'])})")
        print(f"  Target Field: {profile['target_field']}")
        print("  RESULT: PASS")
    except Exception as e:
        print(f"  RESULT: FAIL - {e}")
        all_passed = False
        print("  (Continuing to test writes...)")

    # --- Test 2: Write to Opportunities ---
    print("=" * 50)
    print("TEST 2: Writing test row to Opportunities...")
    try:
        test_data = {
            "job_title": "[TEST] Phase 1 Verification",
            "company": "Test Company",
            "job_url": "https://example.com/test",
            "ats_score": 42,
            "jd_summary": "This is a test row - please delete after verifying",
            "tailored_resume": "Test tailored resume text",
            "founder_name": "Test Founder",
            "founder_linkedin": "https://linkedin.com/in/test",
            "draft_email": "Test draft email content",
        }
        page_id = write_opportunity(client, cfg["NOTION_OPPORTUNITIES_DB_ID"], test_data)
        print(f"  Created Opportunities row: {page_id}")
        print("  RESULT: PASS - Check Notion to verify the row appeared")
    except Exception as e:
        print(f"  RESULT: FAIL - {e}")
        all_passed = False

    # --- Test 3: Write to Run Log ---
    print("=" * 50)
    print("TEST 3: Writing test row to Run Log...")
    try:
        log_data = {
            "trigger_type": "Manual",
            "jobs_found": 0,
            "action_taken": "Phase 1 connectivity verification",
            "status": "Success",
            "error_details": "",
        }
        log_id = write_run_log(client, cfg["NOTION_RUN_LOG_DB_ID"], log_data)
        print(f"  Created Run Log row: {log_id}")
        print("  RESULT: PASS - Check Notion to verify the row appeared")
    except Exception as e:
        print(f"  RESULT: FAIL - {e}")
        all_passed = False

    print("=" * 50)
    if all_passed:
        print("ALL TESTS PASSED - Notion connectivity verified!")
    else:
        print("SOME TESTS FAILED - See details above.")
    print("Please check your Notion databases for the test rows.")
    print("Delete the [TEST] rows after confirming they look correct.")


if __name__ == "__main__":
    main()
