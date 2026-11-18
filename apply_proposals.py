"""Execute only explicitly approved Bellhaven reconciliation proposals.

Project layout:
    bellhaven-crm-sync/
      match.py
      app.py
      apply_proposals.py
      reconcile_output/review_proposals.json
      reconcile_output/review_states.json

Usage:
    pip install requests
    python apply_proposals.py                 # dry run, no writes
    python apply_proposals.py --apply         # prompts for confirmation, writes

Environment:
    CRM_API_TOKEN=your_token
    CRM_BASE_URL=https://analyst-assessment-production.up.railway.app
    CRM_UPDATE_METHOD=PATCH   # change to PUT if Swagger requires PUT (inspect payload semantics first)

Important: this implementation intentionally halts on uncertain identity/state rather
than risk double-creating an account. Re-read account data on each write.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'reconcile_output'
PROPOSALS_FILE = OUT / 'review_proposals.json'
STATE_FILE = OUT / 'review_states.json'
EXECUTION_FILE = OUT / 'execution_states.json'
PARENT_ID = '0015QAPLGS3FVYEEEM'
ALLOWED_FIELDS = {'name','parent_id','billing_street','billing_city','billing_state',
                  'billing_zip','care_type','status','phone','note',
                  'chow_current_account','duplicate_of_account'}
VALID_OPERATIONS = {'UPDATE','CREATE','CHOW','MARK_NEEDS_REVIEW','MARK_INACTIVE_DUPLICATE'}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default):
    if not path.exists():
        if path == STATE_FILE or path == EXECUTION_FILE:
            return default
        raise FileNotFoundError(f'Missing {path}; run python match.py first')
    with path.open('r', encoding='utf-8-sig') as f:
        return json.load(f)


def atomic_save(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(tmp, path)


def signature(p: dict) -> str:
    """Must match app.py EXACTLY; if app signature changes, change this too."""
    significant = {key: p.get(key) for key in
                   ('account_id', 'operation', 'changes', 'create_payload',
                    'candidate_ids', 'review_flags')}
    encoded = json.dumps(significant, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode('utf-8')).hexdigest()


def approved(p: dict, states: dict) -> bool:
    decision = states.get(p['proposal_key'])
    return (isinstance(decision, dict)
            and decision.get('decision') == 'approved'
            and decision.get('signature') == signature(p))


def norm(v):
    return ' '.join(str(v or '').strip().lower().split())


def account_id(a):
    return str(a.get('account_id') or a.get('id') or '') if isinstance(a, dict) else ''


def unwrap_account(data):
    if isinstance(data, dict):
        for field in ('data', 'account'):
            nested = data.get(field)
            if isinstance(nested, dict):
                return nested
        return data
    raise ValueError(f'Unexpected account response type: {type(data).__name__}')


def unwrap_accounts(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for field in ('data','accounts','results'):
            val = data.get(field)
            if isinstance(val, list):
                # Do not silently trust a partial paginated list.
                if data.get('next') or data.get('next_cursor') or data.get('has_more'):
                    raise RuntimeError('CRM accounts response is paginated; implement pagination before CREATE/CHOW')
                return val
            if isinstance(val, dict) and isinstance(val.get('accounts'), list):
                if val.get('next') or val.get('next_cursor') or val.get('has_more'):
                    raise RuntimeError('CRM accounts response is paginated; implement pagination before CREATE/CHOW')
                return val['accounts']
    raise ValueError('Unexpected /accounts response; cannot ensure no duplicates')


class CRMClient:
    def __init__(self, base_url: str, token: str, update_method: str = 'PATCH'):
        base = base_url.rstrip('/')
        self.base_url = base if base.endswith('/api/v1') else base + '/api/v1'
        self.update_method = update_method.upper()
        if self.update_method != 'PATCH':
            raise ValueError('Only PATCH implemented safely; verify API docs before changing to PUT')
        self.session = requests.Session()
        self.session.headers.update({'Authorization': f'Bearer {token}',
                                     'Content-Type': 'application/json', 'Accept': 'application/json'})

    def request(self, method, endpoint, payload=None):
        url = f'{self.base_url}/{endpoint.lstrip("/")}'
        resp = self.session.request(method, url, json=payload, timeout=30)
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f'{method} {endpoint}: HTTP {resp.status_code}: {resp.text[:500]}') from exc
        return resp.json() if resp.content else {}

    def get(self, aid):
        data = self.request('GET', f'accounts/{aid}')
        result = unwrap_account(data)
        if account_id(result) and account_id(result) != aid:
            raise RuntimeError(f'GET account ID mismatch: expected {aid}, got {account_id(result)}')
        return result

    def list_accounts(self):
        return unwrap_accounts(self.request('GET', 'accounts'))

    def create(self, payload):
        data = self.request('POST', 'accounts', payload)
        obj = unwrap_account(data)
        new_id = account_id(obj)
        if not new_id:
            raise RuntimeError(f'POST succeeded but response has no account id; inspect CRM before retry: {data}')
        return new_id

    def patch(self, aid, payload):
        return self.request('PATCH', f'accounts/{aid}', payload)


def changes_payload(p):
    out = {}
    for item in p.get('changes') or []:
        field = item['field']
        if field not in ALLOWED_FIELDS or field in out:
            raise ValueError(f'Unsafe or repeated change field: {field}')
        out[field] = item['to']
    return out


def same_identity(acct, payload):
    """Conservative comparison of address + city/state/ZIP; avoid name-only matching."""
    return all(norm(acct.get(k)) == norm(payload.get(k)) for k in
               ('billing_street','billing_city','billing_state','billing_zip'))


def matching_new_accounts(client, payload):
    same_location = [a for a in client.list_accounts() if same_identity(a, payload)]
    return same_location


def validate_financial_chow(old, desired_parent):
    revenue = float(old.get('lifetime_revenue') or 0)
    ar = float(old.get('outstanding_ar') or 0)
    if not (revenue > 0 and ar > 0):
        raise RuntimeError('CHOW condition no longer holds; re-run match.py and re-approve')
    if norm(old.get('parent_id')) == norm(desired_parent):
        raise RuntimeError('Old CHOW account already has the target parent; manual investigation required')


def execute_one(p, client, journal):
    key = p['proposal_key']
    sig = signature(p)
    op = p['operation']
    row = journal.get(key) or {}
    if row and row.get('signature') != sig:
        raise RuntimeError('Proposal changed after previous execution attempt; inspect execution_states.json')
    if row.get('status') == 'applied':
        return 'skipped'
    if op not in VALID_OPERATIONS:
        raise ValueError(f'Unsupported operation: {op}')

    def checkpoint(status, **extra):
        record = dict(journal.get(key) or {})
        record.update({'signature': sig, 'status': status, 'updated_at': utc_now(),
                       'facility': p.get('facility'), 'operation': op, **extra})
        journal[key] = record
        atomic_save(EXECUTION_FILE, journal)

    if op in {'UPDATE','MARK_NEEDS_REVIEW','MARK_INACTIVE_DUPLICATE'}:
        aid = p.get('account_id')
        if not aid:
            raise ValueError('UPDATE requires an account_id')
        payload = changes_payload(p)
        if not payload:
            raise ValueError('Empty UPDATE payload')
        if 'parent_id' in payload and payload['parent_id'] == PARENT_ID:
            current = client.get(aid)
            if float(current.get('lifetime_revenue') or 0) > 0 and float(current.get('outstanding_ar') or 0) > 0:
                raise RuntimeError('SOP: cannot re-parent revenue+AR account; must use CHOW instead')
        current = client.get(aid)
        to_write = {}
        for c in p['changes']:
            field, expected, target = c['field'], c['from'], c['to']
            value = current.get(field)
            if value == target or norm(value) == norm(target):
                continue
            if norm(value) != norm(expected):
                raise RuntimeError(f'Conflicting live value for {field}: {value!r}; expected {expected!r}. Reconcile again')
            to_write[field] = target
        if to_write:
            client.patch(aid, to_write)
        after = client.get(aid)
        if any(norm(after.get(field)) != norm(target) for field, target in payload.items()):
            raise RuntimeError('PATCH response succeeded but CRM verification failed; do not retry blindly')
        checkpoint('applied', account_id=aid)
        return 'applied'

    payload = p.get('create_payload')
    if not isinstance(payload, dict) or not payload.get('name') or not payload.get('parent_id'):
        raise ValueError('CREATE/CHOW requires a valid create_payload')
    if any(k not in ALLOWED_FIELDS for k in payload):
        raise ValueError('CREATE payload contains fields not allowed by executor')
    if payload['parent_id'] != PARENT_ID:
        raise ValueError('CREATE parent_id is not Bellhaven')

    if op == 'CHOW':
        old_id = p.get('account_id')
        if not old_id:
            raise ValueError('CHOW requires old account_id')
        old = client.get(old_id)
        validate_financial_chow(old, payload['parent_id'])
        linked = str(old.get('chow_current_account') or '')
    else:
        old_id = None
        linked = ''

    new_id = row.get('new_account_id')
    if new_id:
        existing = client.get(new_id)
        if not same_identity(existing, payload) or norm(existing.get('parent_id')) != norm(payload['parent_id']):
            raise RuntimeError('Journal new_account_id does not match expected facility')
    elif linked:
        # CHOW may have succeeded in a previous run before journal checkpoint.
        existing = client.get(linked)
        if not same_identity(existing, payload) or norm(existing.get('parent_id')) != norm(payload['parent_id']):
            raise RuntimeError('Existing CHOW link points to another facility; stop for investigation')
        new_id = linked
        checkpoint('created', new_account_id=new_id)
    else:
        candidates = matching_new_accounts(client, payload)
        if candidates:
            details = ', '.join(f'{account_id(a)} ({a.get("name")}, parent={a.get("parent_id")})' for a in candidates)
            # Fail closed: could be a historical record or concurrent creation.
            raise RuntimeError('Same-address account(s) exist; cannot safely auto-create: ' + details)
        # Avoid automatically retrying POST if previous attempt had unknown outcome.
        if row.get('status') == 'creating':
            raise RuntimeError('Previous create outcome unknown. Check CRM manually before retrying')
        checkpoint('creating')
        new_id = client.create(payload)
        checkpoint('created', new_account_id=new_id)

    if op == 'CHOW':
        old = client.get(old_id)
        linked = str(old.get('chow_current_account') or '')
        if linked and linked != new_id:
            raise RuntimeError(f'Old account already linked to {linked}, expected {new_id}')
        if not linked:
            # SOP requires old account left untouched EXCEPT chow_current_account.
            client.patch(old_id, {'chow_current_account': new_id})
        old_after = client.get(old_id)
        if str(old_after.get('chow_current_account') or '') != new_id:
            raise RuntimeError('CHOW link not verified; account created but not marked applied')
        checkpoint('applied', new_account_id=new_id, old_account_id=old_id)
    else:
        new = client.get(new_id)
        if not same_identity(new, payload) or norm(new.get('parent_id')) != norm(payload['parent_id']):
            raise RuntimeError('Created account verification failed')
        checkpoint('applied', new_account_id=new_id)
    return 'applied'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='Actually write approved proposals to CRM')
    args = parser.parse_args()
    proposals = load_json(PROPOSALS_FILE, [])
    decisions = load_json(STATE_FILE, {})
    journal = load_json(EXECUTION_FILE, {})
    if not isinstance(proposals, list) or not isinstance(decisions, dict) or not isinstance(journal, dict):
        raise ValueError('Invalid JSON format')
    eligible = [p for p in proposals if approved(p, decisions)]
    invalid_approvals = [p.get('proposal_key') for p in proposals
                         if isinstance(decisions.get(p.get('proposal_key')), dict)
                         and decisions[p['proposal_key']].get('decision') == 'approved'
                         and not approved(p, decisions)]
    print(f'Total proposals: {len(proposals)} | Valid approved: {len(eligible)} | Stale approvals: {len(invalid_approvals)}')
    for key in invalid_approvals:
        print('  STALE approval - requires re-review:', key)
    for p in eligible:
        prior = journal.get(p['proposal_key']) or {}
        state = 'APPLIED' if prior.get('status') == 'applied' else prior.get('status', 'PENDING')
        print(f"  [{state}] {p['operation']:<24} {p['facility']}")
    if not args.apply:
        print('\nDRY RUN ONLY. To execute, run: python apply_proposals.py --apply')
        return
    if not eligible:
        print('No valid approved proposals to apply.')
        return
    token = os.environ.get('CRM_API_TOKEN') or os.environ.get('API_TOKEN')
    if not token:
        raise RuntimeError('Set CRM_API_TOKEN in your environment (do not hardcode it)')
    base_url = os.environ.get('CRM_BASE_URL', 'https://analyst-assessment-production.up.railway.app')
    method = os.environ.get('CRM_UPDATE_METHOD', 'PATCH')
    client = CRMClient(base_url, token, method)
    if input('\nType APPLY to write approved proposals to CRM: ').strip() != 'APPLY':
        print('Cancelled')
        return
    count_ok = count_skip = count_fail = 0
    for i, p in enumerate(eligible, start=1):
        print(f"[{i}/{len(eligible)}] {p['operation']}: {p['facility']}")
        try:
            result = execute_one(p, client, journal)
            if result == 'skipped':
                count_skip += 1
            else:
                count_ok += 1
            print('  ->', result)
        except (requests.RequestException, ValueError, RuntimeError, KeyError) as exc:
            count_fail += 1
            print('  -> FAILED:', exc)
            # Preserve journal state (e.g., creating/created) for safe resume.
    print(f'Finished: applied={count_ok} skipped={count_skip} failed={count_fail}')
    print('Execution journal:', EXECUTION_FILE)


if __name__ == '__main__':
    main()
