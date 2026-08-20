"""
Notion operations module.
All reads/writes to the three Notion databases go through here.
Profile data is read into memory and never persisted to disk.

Uses notion-client v3.x with API version pinned to 2022-06-28
which supports databases/query.

Notion DB property names:
  Profile:       Name (title), Resume (files -> PDF parsed in-memory), Additional Info (rich_text), Target Field (rich_text)
  Opportunities: Job Title (title), Company (rich_text), Job Link (url), Status (select),
                 ATS Score (number), JD Summary (rich_text), Tailored Resume (rich_text),
                 Founder Name (rich_text), Founder LinkedIn (url), Draft Email (rich_text),
                 Date Found (date)
  Run Log:       Run ID (title), Timestamp (date), Trigger Type (select), Jobs Found (number),
                 Action Taken (rich_text), Errors/Notes (rich_text), Status (select)
"""

import io
from datetime import datetime, timezone
import requests
from pypdf import PdfReader
from notion_client import Client


def get_notion_client(token: str) -> Client:
    """Initialize and return a Notion SDK client.

    Pins to Notion API version 2022-06-28 which supports databases/query.
    """
    return Client(auth=token, notion_version="2022-06-28")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_rich_text(prop: dict) -> str:
    """Extract plain text from a rich_text property."""
    return "".join(seg.get("plain_text", "") for seg in prop.get("rich_text", []))


def _extract_title(prop: dict) -> str:
    """Extract plain text from a title property."""
    return "".join(seg.get("plain_text", "") for seg in prop.get("title", []))


def _extract_pdf_text_from_file_prop(prop: dict) -> str:
    """Download PDF into an in-memory stream and extract text. Zero disk writes."""
    files = prop.get("files", [])
    if not files:
        return ""
    
    file_obj = files[0]
    file_type = file_obj.get("type")
    
    if file_type == "file":
        url = file_obj.get("file", {}).get("url")
    elif file_type == "external":
        url = file_obj.get("external", {}).get("url")
    else:
        return ""

    if not url:
        return ""

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    # Read strictly in memory using BytesIO
    pdf_stream = io.BytesIO(response.content)
    reader = PdfReader(pdf_stream)
    text_content = []
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text_content.append(extracted)
            
    return "\n".join(text_content).strip()


def _query_database(client: Client, db_id: str, filter_obj: dict = None,
                    page_size: int = 100) -> list:
    """
    Query a Notion database using the raw request method.
    Returns list of page results.
    """
    body = {"page_size": page_size}
    if filter_obj:
        body["filter"] = filter_obj
    response = client.request(
        path=f"databases/{db_id}/query",
        method="POST",
        body=body,
    )
    return response.get("results", [])


# ---------------------------------------------------------------------------
# Profile Database — READ ONLY (never write personal data to disk)
# ---------------------------------------------------------------------------

def read_profile(client: Client, profile_db_id: str) -> dict:
    """
    Read the first row from the Profile database.
    Extracts PDF resume text strictly in-memory.
    Returns dict: name, resume_text, additional_info, target_field.
    """
    results = _query_database(client, profile_db_id, page_size=1)
    if not results:
        raise ValueError("Profile database is empty. Please add your profile row with the PDF resume.")

    props = results[0]["properties"]
    
    resume_text = _extract_pdf_text_from_file_prop(props.get("Resume", {}))
    if not resume_text:
        # Fallback if Resume Text exists as rich text
        resume_text = _extract_rich_text(props.get("Resume Text", {}))

    return {
        "name": _extract_title(props.get("Name", {})),
        "resume_text": resume_text,
        "additional_info": _extract_rich_text(props.get("Additional Info", {})),
        "target_field": _extract_rich_text(props.get("Target Field", {})),
    }


# ---------------------------------------------------------------------------
# Opportunities Database — WRITE
# ---------------------------------------------------------------------------

def write_opportunity(client: Client, db_id: str, data: dict) -> str:
    """
    Write one opportunity row to the Opportunities database.
    data keys: job_title, company, job_url, ats_score, jd_summary,
               tailored_resume, founder_name, founder_linkedin, draft_email
    Returns the created page ID.
    """
    now = datetime.now(timezone.utc).date().isoformat()

    properties = {
        "Job Title": {"title": [{"text": {"content": data.get("job_title", "")[:2000]}}]},
        "Company": {"rich_text": [{"text": {"content": data.get("company", "")[:2000]}}]},
        "Job Link": {"url": data.get("job_url", "") or None},
        "Status": {"select": {"name": "Pending Approval"}},
        "ATS Score": {"number": data.get("ats_score", 0)},
        "JD Summary": {"rich_text": [{"text": {"content": data.get("jd_summary", "")[:2000]}}]},
        "Tailored Resume": {"rich_text": [{"text": {"content": data.get("tailored_resume", "")[:2000]}}]},
        "Founder Name": {"rich_text": [{"text": {"content": data.get("founder_name", "")[:2000]}}]},
        "Founder LinkedIn": {"url": data.get("founder_linkedin", "") or None},
        "Draft Email": {"rich_text": [{"text": {"content": data.get("draft_email", "")[:2000]}}]},
        "Company Email": {"email": data.get("company_email", "") or None},
        "Date Found": {"date": {"start": now}},
    }
    page = client.pages.create(parent={"database_id": db_id}, properties=properties)
    return page["id"]


# ---------------------------------------------------------------------------
# Run Log Database — WRITE
# ---------------------------------------------------------------------------

def write_run_log(client: Client, db_id: str, data: dict) -> str:
    """
    Write one row to the Run Log database.
    data keys: trigger_type, jobs_found, action_taken, status, error_details
    Returns the created page ID.
    """
    now = datetime.now(timezone.utc)
    run_id = f"Run-{now.strftime('%Y-%m-%d-%H:%M:%S')}"

    properties = {
        "Run ID": {"title": [{"text": {"content": run_id}}]},
        "Timestamp": {"date": {"start": now.isoformat()}},
        "Trigger Type": {"select": {"name": data.get("trigger_type", "Manual")}},
        "Jobs Found": {"number": data.get("jobs_found", 0)},
        "Action Taken": {"rich_text": [{"text": {"content": data.get("action_taken", "")[:2000]}}]},
        "Status": {"select": {"name": data.get("status", "Success")}},
        "Errors/Notes": {"rich_text": [{"text": {"content": data.get("error_details", "")[:2000]}}]},
    }
    page = client.pages.create(parent={"database_id": db_id}, properties=properties)
    return page["id"]


# ---------------------------------------------------------------------------
# Opportunities Database — READ (for send_approved.py)
# ---------------------------------------------------------------------------

def query_approved_opportunities(client: Client, db_id: str) -> list:
    """Query opportunities with Status == 'Approved'."""
    filter_obj = {
        "property": "Status",
        "select": {"equals": "Approved"},
    }
    results = _query_database(client, db_id, filter_obj=filter_obj)

    opportunities = []
    for page in results:
        props = page["properties"]
        opportunities.append({
            "page_id": page["id"],
            "job_title": _extract_title(props.get("Job Title", {})),
            "company": _extract_rich_text(props.get("Company", {})),
            "job_url": props.get("Job Link", {}).get("url", ""),
            "ats_score": props.get("ATS Score", {}).get("number", 0),
            "tailored_resume": _extract_rich_text(props.get("Tailored Resume", {})),
            "founder_name": _extract_rich_text(props.get("Founder Name", {})),
            "founder_linkedin": props.get("Founder LinkedIn", {}).get("url", ""),
            "draft_email": _extract_rich_text(props.get("Draft Email", {})),
            "company_email": props.get("Company Email", {}).get("email", "") or "",
        })
    return opportunities


def update_opportunity_status(client: Client, page_id: str, new_status: str):
    """Update the Status select property of an opportunity page."""
    client.pages.update(
        page_id=page_id,
        properties={"Status": {"select": {"name": new_status}}},
    )
