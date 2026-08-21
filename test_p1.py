"""Test P1: Verify candidate name flows correctly from Notion without hardcode."""
from dotenv import load_dotenv
load_dotenv()
from config import get_config
from notion_ops import get_notion_client, read_profile
from llm_pipeline import draft_outreach_email
from groq import Groq

cfg = get_config()
groq = Groq(api_key=cfg['GROQ_API_KEY'])
c = get_notion_client(cfg['NOTION_TOKEN'])
profile = read_profile(c, cfg['NOTION_PROFILE_DB_ID'])

candidate_name = profile.get("name", "Candidate")
resume_text = profile.get("resume_text", "")

print(f"Name from Notion Profile: '{candidate_name}'")

draft = draft_outreach_email(
    groq,
    candidate_name,
    "Proton Solutions",
    "AI Engineer Internship",
    "",
    ["Python", "AI/ML"],
    resume_text,
    "Proton Solutions builds privacy-focused email and VPN tools."
)

print(f"\n--- DRAFT ---")
print(draft)
print(f"--- END ---")

# Check signature
if "Deepanshu Tevathiya" in draft:
    print("\n[PASS] Correct name 'Deepanshu Tevathiya' found in draft.")
elif "Deepabshu" in draft:
    print("\n[FAIL] Old typo 'Deepabshu' still in draft!")
else:
    print("\n[WARN] Name not found in draft at all.")
