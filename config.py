import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://analyst-assessment-production.up.railway.app"
API_BASE = f"{BASE_URL}/api/v1"

API_TOKEN = os.getenv("CRM_API_TOKEN", "YOUR_TOKEN_HERE")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

BELLHAVEN_PARENT_ID = "0015QAPLGS3FVYEEEM"
BELLHAVEN_PARENT_NAME = "Bellhaven Senior Living (Parent Account)"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

SCRAPED_FILE = os.path.join(DATA_DIR, "scraped_locations.json")
CRM_SNAPSHOT_FILE = os.path.join(DATA_DIR, "crm_snapshot.json")
PROPOSALS_FILE = os.path.join(DATA_DIR, "proposals.json")
STATE_FILE = os.path.join(DATA_DIR, "review_state.json")