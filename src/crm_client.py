"""Bellhaven CRM API client with safe account pagination."""
from __future__ import annotations

import requests


class CRMClient:
    def __init__(self, base_url: str, api_token: str):
        if not api_token:
            raise ValueError("Missing CRM_API_TOKEN")
        base_url = base_url.rstrip("/")
        self.base_url = base_url if base_url.endswith("/api/v1") else f"{base_url}/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _request(self, method: str, endpoint: str, *, params=None, payload=None):
        response = self.session.request(
            method, f"{self.base_url}/{endpoint.lstrip('/')}",
            params=params, json=payload, timeout=30,
        )
        response.raise_for_status()
        return response.json() if response.content else {}

    def get_accounts(self, page_size: int = 100, max_pages: int = 1000) -> list[dict]:
        """Fetch ALL account pages. The server may enforce a smaller page size."""
        if page_size < 1 or max_pages < 1:
            raise ValueError("page_size and max_pages must be positive")

        accounts: list[dict] = []
        seen_ids: set[str] = set()
        previous_page_ids: set[str] | None = None
        expected_total: int | None = None
        finished = False

        for page in range(1, max_pages + 1):
            response = self._request(
                "GET", "accounts", params={"page": page, "page_size": page_size}
            )

            if isinstance(response, list):
                items = response
                meta = {}
            elif isinstance(response, dict):
                items = response.get("data")
                if items is None:
                    items = response.get("accounts")
                if items is None:
                    items = response.get("results")
                if not isinstance(items, list):
                    raise ValueError(f"Page {page}: unrecognized accounts response structure")
                meta = response
                pagination = response.get("pagination")
                if isinstance(pagination, dict):
                    meta = {**pagination, **response}
            else:
                raise ValueError(f"Page {page}: invalid JSON response type")

            total = meta.get("total")
            if total is None:
                total = meta.get("total_count")
            if total is not None:
                total = int(total)
                if expected_total is None:
                    expected_total = total
                elif expected_total != total:
                    raise RuntimeError("CRM total changed during pagination; retry snapshot")

            if not items:
                if expected_total is not None and len(accounts) != expected_total:
                    raise RuntimeError(
                        f"Only fetched {len(accounts)} accounts but API total is {expected_total}"
                    )
                print(f"Page {page}: no more accounts")
                finished = True
                break

            page_ids = []
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError(f"Page {page}: account must be an object")
                account_id = item.get("account_id") or item.get("id")
                if not account_id:
                    raise ValueError(f"Page {page}: missing account_id")
                page_ids.append(str(account_id))

            current_ids = set(page_ids)
            if len(current_ids) != len(page_ids):
                raise RuntimeError(f"Page {page}: duplicate account IDs within same page")
            if previous_page_ids == current_ids:
                raise RuntimeError(
                    "Same page returned twice. API may be ignoring the page parameter."
                )
            duplicates = current_ids & seen_ids
            if duplicates:
                raise RuntimeError(
                    f"Page {page}: duplicate IDs across pages (example: {next(iter(duplicates))}); "
                    "snapshot not saved to prevent data loss"
                )
            previous_page_ids = current_ids
            seen_ids.update(current_ids)
            accounts.extend(items)
            print(f"Page {page}: +{len(items)} accounts; cumulative {len(accounts)}")

            if expected_total is not None and len(accounts) >= expected_total:
                if len(accounts) != expected_total:
                    raise RuntimeError("Received more accounts than API reported total")
                finished = True
                break

            # Don't stop merely because len(items) < requested page_size:
            # the server may impose its own smaller page limit.
            if meta.get("has_more") is False or meta.get("has_next") is False:
                if expected_total is not None and len(accounts) != expected_total:
                    raise RuntimeError("has_more=False conflicts with total")
                finished = True
                break

        if not finished:
            raise RuntimeError(f"Reached max_pages={max_pages} without reaching end of CRM")
        return accounts

    # Backward compatible with existing save_snapshot.py
    def get_customers(self, page_size: int = 100) -> list[dict]:
        return self.get_accounts(page_size=page_size)

    # Existing API operations for other components
    def get_account(self, account_id: str):
        return self._request("GET", f"accounts/{account_id}")

    def create_account(self, payload: dict):
        return self._request("POST", "accounts", payload=payload)

    def update_account(self, account_id: str, changes: dict):
        return self._request("PATCH", f"accounts/{account_id}", payload=changes)
