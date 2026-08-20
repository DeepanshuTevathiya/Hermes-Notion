import requests, os
from dotenv import load_dotenv; load_dotenv()
from config import get_config
cfg = get_config()
url = f"https://api.notion.com/v1/databases/{cfg['NOTION_OPPORTUNITIES_DB_ID']}"
headers = {
    'Authorization': f"Bearer {cfg['NOTION_TOKEN']}",
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json'
}
data = {
    'properties': {
        'Needs Manual Review': {
            'checkbox': {}
        }
    }
}
resp = requests.patch(url, headers=headers, json=data)
print(resp.status_code)
print(resp.json())
