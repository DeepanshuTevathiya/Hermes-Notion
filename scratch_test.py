"""Update Fortune Analytics draft email in Notion with the new personalized format."""
import os
from dotenv import load_dotenv
load_dotenv()

from config import get_config
from notion_ops import get_notion_client, read_profile
from llm_pipeline import draft_outreach_email
from scraper import extract_company_context, find_company_website
from groq import Groq
from notion_client import Client

cfg = get_config()
groq = Groq(api_key=cfg['GROQ_API_KEY'])
c = Client(auth=cfg['NOTION_TOKEN'], notion_version='2022-06-28')

profile = read_profile(c, cfg['NOTION_PROFILE_DB_ID'])
resume_text = profile['resume_text']

# Find Fortune Analytics row
opp_res = c.request(
    path=f"databases/{cfg['NOTION_OPPORTUNITIES_DB_ID']}/query",
    method="POST",
    body={"page_size": 100},
)
fortune_page_id = None
job_title = "AI Engineer Internship"
old_draft = ""
for o in opp_res.get("results", []):
    props = o["properties"]
    comp = "".join(t.get("plain_text", "") for t in props.get("Company", {}).get("rich_text", []))
    if "Fortune Analytics" in comp:
        fortune_page_id = o["id"]
        job_title = "".join(t.get("plain_text", "") for t in props.get("Job Title", {}).get("title", []))
        old_draft = "".join(t.get("plain_text", "") for t in props.get("Draft Email", {}).get("rich_text", []))
        break

if not fortune_page_id:
    print("Fortune Analytics row not found!")
    exit(1)

print("=== BEFORE ===")
print(old_draft)
print()

# Get company context
search_hint = f"{job_title} startup OR careers"
website = find_company_website("Fortune Analytics", search_hint=search_hint)
context = extract_company_context(website, company_name="Fortune Analytics")
print(f"Website: {website}")
print(f"Context length: {len(context)} chars")
print()

# Generate new draft
new_draft = draft_outreach_email(
    groq,
    "Deepanshu Tevathiya",
    "Fortune Analytics",
    job_title,
    "",
    ["Python", "AI/ML", "Data Science"],
    resume_text,
    context,
)

print("=== AFTER ===")
print(new_draft)
print()

# Update Notion
needs_review = not bool(context)
c.pages.update(
    page_id=fortune_page_id,
    properties={
        "Draft Email": {"rich_text": [{"text": {"content": new_draft[:2000]}}]},
        "Needs Manual Review": {"checkbox": needs_review},
    },
)
print(f"Updated Fortune Analytics in Notion (Needs Review: {needs_review}).")
