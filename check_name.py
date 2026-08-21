from dotenv import load_dotenv
load_dotenv()
from config import get_config
from notion_ops import get_notion_client, read_profile

cfg = get_config()
c = get_notion_client(cfg['NOTION_TOKEN'])
profile = read_profile(c, cfg['NOTION_PROFILE_DB_ID'])

print(f"Name from Notion Profile DB: '{profile['name']}'")
print(f"Resume text first 200 chars: '{profile['resume_text'][:200]}'")
