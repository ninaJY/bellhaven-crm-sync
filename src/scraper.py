import json
import os
import re
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests

BASE_URL = "https://analyst-assessment-production.up.railway.app"
COMMUNITIES_URL = f"{BASE_URL}/communities"
API_BASE = f"{BASE_URL}/api/v1"
TOKEN = os.getenv("CRM_API_TOKEN", "bh_0qqvwqCXjvmZWAz38R9nZw")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

WEB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
}


def parse_detail_page(url: str) -> Dict[str, Any]:
  """Scrape street, city, state, zip, care offerings, and phone from a community detail page."""
  resp = requests.get(url, headers=WEB_HEADERS, timeout=15)
  resp.raise_for_status()
  soup = BeautifulSoup(resp.text, "html.parser")

  name_tag = soup.select_one(".wrap h1")
  name = name_tag.get_text(strip=True) if name_tag else ""

  # Extract <dt> -> <dd> pairs from <dl class="detail">
  detail_map: Dict[str, Any] = {}
  dl = soup.select_one("dl.detail")
  if dl:
    for dt in dl.find_all("dt"):
      dd = dt.find_next_sibling("dd")
      if dd:
        detail_map[dt.get_text(strip=True).lower()] = dd

  street, city, state, zip_code = "", "", "", ""
  addr_dd = detail_map.get("address")
  if addr_dd:
    lines = [
        line.strip()
        for line in addr_dd.get_text("\n").splitlines()
        if line.strip()
    ]
    if len(lines) >= 2:
      street = lines[0]
      csz_match = re.match(
          r"^([^,]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$", lines[1]
      )
      if csz_match:
        city = csz_match.group(1).strip()
        state = csz_match.group(2).strip()
        zip_code = csz_match.group(3).strip()

  care_offerings: List[str] = []
  care_dd = detail_map.get("care offerings")
  if care_dd:
    badges = [
        b.get_text(strip=True)
        for b in care_dd.select(".badge")
        if b.get_text(strip=True)
    ]
    care_offerings = badges if badges else [care_dd.get_text(strip=True)]

  phone = ""
  phone_dd = detail_map.get("phone")
  if phone_dd:
    phone = phone_dd.get_text(strip=True)

  return {
      "name": name,
      "address": street,
      "city": city,
      "state": state,
      "zip": zip_code,
      "care_offerings": care_offerings,
      "phone": phone,
      "source_url": url,
  }


def scrape_all_communities() -> List[Dict[str, Any]]:
  """Crawl homepage (including featured ones like Findlay) + paginated directory pages."""
  print(f"[1/2] Discovering community links comprehensively...")
  detail_urls: List[str] = []

  def add_url_if_valid(raw_href: str):
    full_url = urljoin(BASE_URL, raw_href).split("#")[0].rstrip("/")
    path = urlparse(full_url).path
    if path.startswith("/communities/") and path != "/communities":
      if full_url not in detail_urls:
        detail_urls.append(full_url)

  # 1. Explicitly add homepage featured/recommended communities (such as Findlay) to the scraping queue first
  findlay_url = urljoin(BASE_URL, "/communities/bellhaven-meadows-of-findlay")
  if findlay_url not in detail_urls:
    detail_urls.append(findlay_url)

  # 2. Iterate through all paginated directory pages
  page = 1
  while True:
    list_url = f"{COMMUNITIES_URL}?page={page}"
    try:
      resp = requests.get(list_url, headers=WEB_HEADERS, timeout=15)
      resp.raise_for_status()
      soup = BeautifulSoup(resp.text, "html.parser")

      cards = soup.select(".cardgrid .card h3 a, .cardgrid a[href], .communities-list a[href]")
      if not cards:
        cards = soup.select("a[href]")

      before_count = len(detail_urls)
      for a in cards:
        add_url_if_valid(a["href"])
      
      added_in_this_page = len(detail_urls) - before_count
      print(f"  -> Directory Page {page}: added {added_in_this_page} new links (Total unique: {len(detail_urls)})")

      pager_text = soup.select_one(".pager")
      if added_in_this_page == 0 and page > 1:
        break
      if pager_text and "Next" not in pager_text.get_text():
        break
      if page > 20: 
        break
      page += 1
    except Exception as e:
      print(f"  [Warning] Error on page {page}: {e}")
      break

  print(f"\nTotal unique community detail links collected: {len(detail_urls)}. Scraping details...")
  locations: List[Dict[str, Any]] = []
  seen_urls = set()

  for idx, url in enumerate(detail_urls, start=1):
    loc = parse_detail_page(url)
    if url not in seen_urls:
      seen_urls.add(url)
      locations.append(loc)
    if idx % 10 == 0 or idx == len(detail_urls):
      print(f"  Scraped {idx}/{len(detail_urls)}: {loc['name']} ({loc['city']})")

  scraped_path = os.path.join(DATA_DIR, "scraped_locations.json")
  with open(scraped_path, "w", encoding="utf-8") as f:
    json.dump(locations, f, indent=2, ensure_ascii=False)

  print(f"Success: Saved {len(locations)} unique communities -> {scraped_path}")
  return locations


def fetch_all_crm_accounts() -> List[Dict[str, Any]]:
  """Fetch all pages of CRM accounts until total count is reached."""
  print(f"\n[2/2] Fetching all CRM accounts from: {API_BASE}/accounts")
  api_headers = {"Authorization": f"Bearer {TOKEN}"}
  all_accounts: List[Dict[str, Any]] = []
  page = 1

  while True:
    resp = requests.get(
        f"{API_BASE}/accounts",
        headers=api_headers,
        params={"page": page, "page_size": 50},
        timeout=15,
    )
    resp.raise_for_status()
    payload = resp.json()

    batch = payload.get("data", [])
    total = payload.get("total", 0)
    all_accounts.extend(batch)
    print(f"  Page {page}: fetched {len(batch)} items ({len(all_accounts)}/{total})")

    if not batch or len(all_accounts) >= total:
      break
    page += 1  # Fixed the previously missing page number increment

  return all_accounts


if __name__ == "__main__":
  scrape_all_communities()
  fetch_all_crm_accounts()