from dotenv import load_dotenv
load_dotenv()
from config import get_config
from notion_client import Client

cfg = get_config()
c = Client(auth=cfg['NOTION_TOKEN'], notion_version='2022-06-28')
db_id = cfg['NOTION_OPPORTUNITIES_DB_ID']
opp_res = c.request(path=f"databases/{db_id}/query", method="POST", body={"page_size": 20})
for o in opp_res.get("results", []):
    props = o["properties"]
    comp = "".join(t.get("plain_text", "") for t in props.get("Company", {}).get("rich_text", []))
    status = props.get("Status", {}).get("select", {}).get("name", "N/A")
    print(f"{comp}: {status}")
