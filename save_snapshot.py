"""Download all CRM accounts and atomically replace the local snapshot."""
import json
import os
from pathlib import Path

from config import BASE_URL, API_TOKEN, CRM_SNAPSHOT_FILE
from src.crm_client import CRMClient


def save_crm_snapshot():
    print("Fetching ALL CRM accounts (paginated)...")
    if not API_TOKEN:
        raise RuntimeError("CRM_API_TOKEN is not set")

    client = CRMClient(base_url=BASE_URL, api_token=API_TOKEN)
    try:
        accounts = client.get_customers(page_size=100)
    finally:
        client.session.close()

    if not accounts:
        raise RuntimeError("CRM returned zero accounts; existing snapshot was preserved")

    ids = [str(a.get("account_id") or a.get("id")) for a in accounts]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Duplicate account IDs; existing snapshot was preserved")

    path = Path(CRM_SNAPSHOT_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")

    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(accounts, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)  # overwrite only after complete success
    finally:
        if temp_path.exists():
            temp_path.unlink()

    print(f"SUCCESS: saved {len(accounts)} unique CRM accounts to {path}")
    return accounts


if __name__ == "__main__":
    save_crm_snapshot()
