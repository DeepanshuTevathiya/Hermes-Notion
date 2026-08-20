"""
Centralized configuration loader.
Uses python-dotenv for local testing (.env file, gitignored).
On GitHub Actions, env vars are injected from repo Secrets.
Never prints or logs secret values.
"""

import os
import sys
from dotenv import load_dotenv

# Load .env only if it exists (local dev); on Actions, env vars are already set
load_dotenv()

REQUIRED_VARS = [
    "NOTION_TOKEN",
    "NOTION_PROFILE_DB_ID",
    "NOTION_OPPORTUNITIES_DB_ID",
    "NOTION_RUN_LOG_DB_ID",
    "GROQ_API_KEY",
    "GMAIL_USER",
    "GMAIL_APP_PASSWORD",
    "TARGET_FIELD",
]


def get_config():
    """Return a dict of all required config values. Exits if any are missing."""
    config = {}
    missing = []
    for var in REQUIRED_VARS:
        val = os.environ.get(var)
        if not val:
            missing.append(var)
        else:
            config[var] = val
    if missing:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("Set them in .env (local) or GitHub Secrets (Actions).")
        sys.exit(1)
    return config
