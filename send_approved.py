"""
Hermes-Notion Pipeline: send_approved.py
Triggered via GitHub Actions cron every ~15 minutes (or manual trigger).

Human Approval Gate:
1. Queries Notion Opportunities where Status == "Approved".
2. Generates in-memory clean PDF or Text resume attachment (zero disk persistence).
3. Connects to Gmail SMTP (SSL 465) using credentials from GitHub Secrets.
4. Sends cold outreach email with candidate resume attached.
5. Updates the Notion page Status to "Sent".
6. Writes a timestamped log to the Run Log database.
"""

import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone

from config import get_config
from notion_ops import (
    get_notion_client,
    query_approved_opportunities,
    update_opportunity_status,
    write_run_log,
)


def send_email_with_in_memory_resume(
    smtp_user: str,
    smtp_password: str,
    to_email: str,
    subject: str,
    body_text: str,
    candidate_name: str,
    resume_content: str,
):
    """
    Constructs and dispatches email via Gmail SMTP with in-memory resume attachment.
    No file is ever written to disk.
    """
    msg = MIMEMultipart()
    msg["From"] = f"{candidate_name} <{smtp_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    # Attach email body
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    # Attach in-memory resume as a text/markdown file attachment
    if resume_content:
        part = MIMEBase("text", "plain", charset="utf-8")
        part.set_payload(resume_content.encode("utf-8"))
        encoders.encode_base64(part)
        filename = f"{candidate_name.replace(' ', '_')}_Resume.txt"
        part.add_header("Content-Disposition", f"attachment; filename=\"{filename}\"")
        msg.attach(part)

    # Send via secure SSL SMTP
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def run_send_approved(trigger_type: str = "Cron"):
    print(f"=== Starting Hermes-Notion send_approved ({trigger_type}) ===")
    cfg = get_config()
    notion = get_notion_client(cfg["NOTION_TOKEN"])

    smtp_user = cfg["GMAIL_USER"]
    smtp_password = cfg["GMAIL_APP_PASSWORD"]

    errors = []
    sent_count = 0

    try:
        # Step 1: Query Approved rows
        print("[1/3] Querying Opportunities for Status = 'Approved'...")
        approved_ops = query_approved_opportunities(notion, cfg["NOTION_OPPORTUNITIES_DB_ID"])
        print(f"      Found {len(approved_ops)} opportunities marked as 'Approved'.")

        if not approved_ops:
            print("      No approved items waiting to be sent.")
            write_run_log(
                notion,
                cfg["NOTION_RUN_LOG_DB_ID"],
                {
                    "trigger_type": trigger_type,
                    "jobs_found": 0,
                    "action_taken": "Ran approval dispatcher. 0 pending emails to send.",
                    "status": "Success",
                    "error_details": "",
                },
            )
            return

        # Step 2: Send each approved opportunity
        print("[2/3] Dispatching approved emails...")
        for opp in approved_ops:
            page_id = opp["page_id"]
            job_title = opp.get("job_title", "Internship")
            company = opp.get("company", "Company")
            draft_email = opp.get("draft_email", "")
            tailored_resume = opp.get("tailored_resume", "")

            # Parse subject and body from draft
            lines = draft_email.strip().splitlines()
            subject = f"Internship Inquiry: {job_title} - {company}"
            body_lines = []

            for line in lines:
                if line.lower().startswith("subject:"):
                    subject = line.split(":", 1)[1].strip()
                else:
                    body_lines.append(line)

            body_text = "\n".join(body_lines).strip()

            company_email = opp.get("company_email", "").strip()

            if not company_email:
                skip_msg = f"Skipped {job_title} @ {company}: No Company Email set. Fill in the 'Company Email' field in Notion before approving."
                print(f"      [Skip] {skip_msg}")
                errors.append(skip_msg)
                continue

            target_recipient = company_email

            try:
                print(f"      Sending email for: {job_title} @ {company}...")
                send_email_with_in_memory_resume(
                    smtp_user=smtp_user,
                    smtp_password=smtp_password,
                    to_email=target_recipient,
                    subject=subject,
                    body_text=body_text,
                    candidate_name="Deepanshu Tevathiya",
                    resume_content=tailored_resume,
                )

                # Step 3: Update Notion status to "Sent"
                update_opportunity_status(notion, page_id, "Sent")
                print(f"      -> Successfully sent & updated status to 'Sent' for {company}!")
                sent_count += 1

            except Exception as e:
                err_msg = f"Failed to send email for {company}: {str(e)}"
                print(f"      [Error] {err_msg}")
                errors.append(err_msg)

        # Step 4: Record Run Log
        print("[3/3] Writing Run Log...")
        status = "Success"
        if errors:
            status = "Partial" if sent_count > 0 else "Failed"

        action_summary = f"Processed approved queue. Sent {sent_count} outreach email(s)."
        error_summary = "\n".join(errors) if errors else ""

        write_run_log(
            notion,
            cfg["NOTION_RUN_LOG_DB_ID"],
            {
                "trigger_type": trigger_type,
                "jobs_found": sent_count,
                "action_taken": action_summary,
                "status": status,
                "error_details": error_summary,
            },
        )
        print(f"=== send_approved Finished with status: {status} ===")

    except Exception as e:
        err_msg = f"Fatal dispatcher error: {str(e)}"
        print(f"[FATAL ERROR] {err_msg}")
        try:
            write_run_log(
                notion,
                cfg["NOTION_RUN_LOG_DB_ID"],
                {
                    "trigger_type": trigger_type,
                    "jobs_found": 0,
                    "action_taken": "send_approved dispatcher crashed.",
                    "status": "Failed",
                    "error_details": err_msg,
                },
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    trigger = sys.argv[1] if len(sys.argv) > 1 else "Manual"
    run_send_approved(trigger_type=trigger)
