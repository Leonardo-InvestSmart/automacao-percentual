import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEETS_KEYFILE = os.getenv(
    "GOOGLE_SHEETS_KEYFILE",
    "percentual-streamlit-53d33f668e0c.json"
)
SPREADSHEET_ID = os.getenv(
    "SPREADSHEET_ID",
    "1ViUu0vOyBVknyVT1aQGqIu-LXLBDYfXZLs_YsWk6EEk"
)
TENANT_ID     = os.getenv("AZURE_TENANT_ID")
CLIENT_ID     = os.getenv("AZURE_CLIENT_ID")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
EMAIL_USER    = os.getenv("EMAIL_USER")
