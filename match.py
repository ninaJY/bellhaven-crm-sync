#!/usr/bin/env python3
"""Bellhaven website vs CRM reconciliation. READ-ONLY: never calls CRM write APIs.

Usage:
  python bellhaven_reconcile.py
  python bellhaven_reconcile.py --website scraped_locations.json --crm crm_snapshot.json
  python bellhaven_reconcile.py --website other_website.json --crm other_crm.json --out results

Produces:
  facilities_reconciliation.csv     one row for each website facility
  crm_cleanup.csv                   unmatched, duplicate or competing CRM accounts
  review_proposals.json             structured, field-level proposals (no writes)
  summary.json                      category counts and audit totals
  reconcile_report.md               readable grouped report

All change proposals require manual approval. This program does not write to CRM.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

DEFAULT_PARENT_ID = '0015QAPLGS3FVYEEEM'
DEFAULT_WEBSITE_FILE = "data/scraped_locations.json"
DEFAULT_CRM_FILE = "data/crm_snapshot.json"

CATEGORIES = [
    'A_MATCH_NO_CHANGE',
    'B_MINOR_FIELD_UPDATE',
    'C_REPARENT_EXISTING',
    'D_CHOW_CREATE_AND_LINK',
    'E_RENAME_OR_REPARENT',
    'F_CREATE_NEW',
]

# Canonical CRM field semantics: billing_street can be a *billing* address, not
# the physical location address. We therefore never overwrite PO Boxes automatically.
ADDRESS_WORDS = {
    'street': 'st', 'st': 'st', 'avenue': 'ave', 'ave': 'ave',
    'road': 'rd', 'rd': 'rd', 'drive': 'dr', 'dr': 'dr',
    'lane': 'ln', 'ln': 'ln', 'boulevard': 'blvd', 'blvd': 'blvd',
    'northwest': 'nw', 'northeast': 'ne', 'southwest': 'sw', 'southeast': 'se',
    'north': 'n', 'south': 's', 'east': 'e', 'west': 'w',
    'parkway': 'pkwy', 'court': 'ct', 'center': 'ctr', 'centre': 'ctr',
    'pike': 'pike', 'pk': 'pike',
}

# For facilities with several equal-address CRM candidates and no clear
# identity, manual choice is explicit, not inferred as ownership fact.
# The override is ONLY a proposed candidate to review, never an auto approval.
CANDIDATE_REVIEW_HINTS = {
    'bellhaven of kettering': '001WR41PYNWXCAE2X4',
}


def resolve_input(path: str) -> Path:
    """Look in current working directory first, then alongside this script."""
    supplied = Path(path).expanduser()
    if supplied.is_file():
        return supplied
    if not supplied.is_absolute():
        beside_script = Path(__file__).resolve().parent / supplied
        if beside_script.is_file():
            return beside_script
    raise FileNotFoundError(
        f'Cannot find {path!r}. Put {path} in the current folder or next to '
        'bellhaven_reconcile.py, or pass its path with --website / --crm.'
    )


def load_records(path: str) -> list[dict]:
    p = resolve_input(path)
    if p.suffix.lower() in ('.json', '.txt'):
        data = json.loads(p.read_text(encoding='utf-8-sig'))
        if isinstance(data, dict):
            # Support typical API wrappers.
            for k in ('accounts', 'communities', 'locations', 'results', 'data', 'items'):
                if isinstance(data.get(k), list):
                    data = data[k]
                    break
        if not isinstance(data, list):
            raise ValueError(f'{p}: expected a JSON list or standard list wrapper')
        return data
    if p.suffix.lower() == '.csv':
        with p.open(encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))
    raise ValueError(f'Unsupported input format {p.suffix}. Use JSON or CSV.')


def s(value) -> str:
    return str(value or '').strip()


def norm_text(value) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]+', ' ', s(value).lower())).strip()


def norm_address(value) -> str:
    words = norm_text(value).split()
    words = [ADDRESS_WORDS.get(w, w) for w in words]
    # Remove spaces to handle e.g. "Health Care" variants? only street here.
    return ' '.join(words)


def norm_name(value) -> str:
    # Used only for identity comparisons. Preserve original name in output.
    name = norm_text(value)
    return ' '.join({'and': '&', 'centre': 'center'}.get(w, w) for w in name.split())


def norm_phone(value) -> str:
    digits = re.sub(r'\D', '', s(value))
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    return digits


def money(value) -> float:
    try:
        return float(str(value or '0').replace(',', '').replace('$', ''))
    except ValueError:
        return 0.0


def offerings(value) -> list[str]:
    if isinstance(value, list):
        return [s(v) for v in value if s(v)]
    if not value:
        return []
    if isinstance(value, str):
        try:
            x = json.loads(value)
            if isinstance(x, list):
                return [s(v) for v in x]
        except (ValueError, TypeError):
            pass
        return [x.strip() for x in re.split(r'\s*[;|]\s*', value) if x.strip()]
    return []


def care_mapping(cares: list[str]) -> str:
    mapped = set()
    for item in cares:
        n = norm_text(item)
        if 'memory' in n:
            mapped.add('Memory Care')
        elif 'nursing' in n or 'rehabilitation' in n:
            mapped.add('Skilled Nursing')
        elif 'assisted' in n:
            mapped.add('Assisted Living')
        elif 'independent' in n:
            mapped.add('Independent Living')
    # CRM only has one care_type; do not replace it when website has multiple offerings.
    return next(iter(mapped)) if len(mapped) == 1 else ''


def same_place(w: dict, a: dict) -> bool:
    """Strong evidence: city, state, street; ZIP may be stale."""
    return (norm_text(w.get('city')) == norm_text(a.get('billing_city'))
            and norm_text(w.get('state')) == norm_text(a.get('billing_state'))
            and norm_address(w.get('address')) == norm_address(a.get('billing_street')))


def name_similarity(w: dict, a: dict) -> float:
    return SequenceMatcher(None, norm_name(w.get('name')), norm_name(a.get('name'))).ratio()


def score(w: dict, a: dict, parent_id: str) -> float:
    """Only rank already geographically eligible candidates; do not use fuzzy global name matching."""
    name_score = name_similarity(w, a)
    address = same_place(w, a)
    city_state = norm_text(w.get('city')) == norm_text(a.get('billing_city')) and norm_text(w.get('state')) == norm_text(a.get('billing_state'))
    name_exact = norm_name(w.get('name')) == norm_name(a.get('name'))
    zip_exact = s(w.get('zip')) == s(a.get('billing_zip'))
    if not address and not (city_state and name_exact):
        return -1
    return (100 if address else 40) + (45 if name_exact else name_score * 25) + (3 if zip_exact else 0) + (6 if a.get('parent_id') == parent_id else 0) + (3 if norm_phone(w.get('phone')) and norm_phone(w.get('phone')) == norm_phone(a.get('phone')) else 0)


def change(field: str, old, new) -> dict:
    return {'field': field, 'from': old if old is not None else '', 'to': new}


def note_change(a: dict, sentence: str) -> dict | None:
    existing = s(a.get('note'))
    if sentence.lower() in existing.lower():
        return None
    return change('note', existing, (existing + '\n' if existing else '') + sentence)


def field_changes(w: dict, a: dict, parent_id: str, *, update_parent: bool, rename: bool) -> tuple[list[dict], list[str]]:
    changes, warnings = [], []
    if rename and s(a.get('name')) != s(w.get('name')):
        changes.append(change('name', s(a.get('name')), s(w.get('name'))))
    if update_parent and s(a.get('parent_id')) != parent_id:
        changes.append(change('parent_id', s(a.get('parent_id')), parent_id))
    for crm_field, web_field in [('billing_city', 'city'), ('billing_state', 'state'), ('billing_zip', 'zip')]:
        if s(w.get(web_field)) and s(a.get(crm_field)) != s(w.get(web_field)):
            changes.append(change(crm_field, s(a.get(crm_field)), s(w.get(web_field))))
    old_street, new_street = s(a.get('billing_street')), s(w.get('address'))
    if old_street and new_street and norm_address(old_street) != norm_address(new_street):
        if re.search(r'\bp\s*o\s*box\b|\bpo box\b', old_street.lower()):
            warnings.append('CRM billing_street is a PO Box; preserve until billing vs physical address is verified')
            nc = note_change(a, f'Website physical address: {new_street}, {s(w.get("city"))}, {s(w.get("state"))} {s(w.get("zip"))}. Verify whether CRM billing_street should change.')
            if nc: changes.append(nc)
        else:
            warnings.append('Different street address despite matching facility name; verify before approval')
    if norm_phone(a.get('phone')) != norm_phone(w.get('phone')) and s(w.get('phone')):
        changes.append(change('phone', s(a.get('phone')), s(w.get('phone'))))
    website_care = care_mapping(offerings(w.get('care_offerings')))
    if website_care and s(a.get('care_type')) != website_care:
        changes.append(change('care_type', s(a.get('care_type')), website_care))
    if not website_care and len(offerings(w.get('care_offerings'))) > 1:
        warnings.append('Website has multiple care offerings; CRM care_type is single-valued; do not overwrite')
    if s(a.get('status')) != 'Active':
        changes.append(change('status', s(a.get('status')), 'Active'))
    return changes, warnings


def new_account(w: dict, parent_id: str) -> dict:
    return {
        'name': s(w.get('name')),
        'parent_id': parent_id,
        'billing_street': s(w.get('address')),
        'billing_city': s(w.get('city')),
        'billing_state': s(w.get('state')),
        'billing_zip': s(w.get('zip')),
        'care_type': care_mapping(offerings(w.get('care_offerings'))),
        'phone': s(w.get('phone')),
        'status': 'Active',
        'note': ('Website offerings: ' + ', '.join(offerings(w.get('care_offerings')))) if len(offerings(w.get('care_offerings'))) > 1 else '',
    }


def reconcile(website: list[dict], crm: list[dict], parent_id: str) -> tuple[list[dict], list[dict], list[dict]]:
    facility_rows, proposals = [], []
    primary_ids = set()
    matched_by_id = {}
    web_matches = {}

    for idx, w in enumerate(website, 1):
        ranked = sorted(((score(w, a, parent_id), a) for a in crm if s(a.get('account_id'))),
                        key=lambda pair: (-pair[0], -name_similarity(w, pair[1]), s(pair[1].get('account_id'))))
        eligible = [(sc, a) for sc, a in ranked if sc >= 0]
        hint = CANDIDATE_REVIEW_HINTS.get(norm_name(w.get('name')))
        chosen = next((a for _, a in eligible if s(a.get('account_id')) == hint), None) if hint else None
        if chosen is None and eligible:
            chosen = eligible[0][1]
        peers = [a for _, a in eligible if a is not chosen and same_place(w, a)]
        note_flags = []
        if len(eligible) > 1:
            note_flags.append(f'{len(eligible)} geographically plausible CRM candidates; review survivor and other accounts')
        account_id = s(chosen.get('account_id')) if chosen else ''
        if chosen:
            primary_ids.add(account_id)
            matched_by_id[account_id] = w
        changes = []
        create_payload = None
        operation = ''
        if chosen is None:
            category = 'F_CREATE_NEW'
            operation = 'CREATE'
            create_payload = new_account(w, parent_id)
            note_flags.append('No eligible same-address or same-name+city/state CRM match')
        else:
            parent_wrong = s(chosen.get('parent_id')) != parent_id
            name_wrong = norm_name(w.get('name')) != norm_name(chosen.get('name'))
            strong_name_match = norm_name(w.get('name')) == norm_name(chosen.get('name'))
            # Light branding/wording revisions are minor field updates.
            # Major rebrands are kept in category E for prominent review.
            major_rename = name_wrong and name_similarity(w, chosen) < 0.85
            if parent_wrong and money(chosen.get('lifetime_revenue')) > 0 and money(chosen.get('outstanding_ar')) > 0:
                category = 'D_CHOW_CREATE_AND_LINK'
                operation = 'CHOW'
                create_payload = new_account(w, parent_id)
                note_flags.append('SOP: existing account has revenue history AND outstanding AR > 0; DO NOT update old parent or any old fields')
                changes = [change('chow_current_account', s(chosen.get('chow_current_account')), '<NEW_ACCOUNT_ID_AFTER_CREATE>')]
            else:
                changes, field_warnings = field_changes(w, chosen, parent_id, update_parent=parent_wrong, rename=name_wrong)
                note_flags.extend(field_warnings)
                if major_rename:
                    category = 'E_RENAME_OR_REPARENT'
                elif parent_wrong:
                    category = 'C_REPARENT_EXISTING'
                elif changes:
                    category = 'B_MINOR_FIELD_UPDATE'
                else:
                    category = 'A_MATCH_NO_CHANGE'
                operation = 'NONE' if not changes else 'UPDATE'
            for peer in peers:
                web_matches[s(peer['account_id'])] = {'site': w, 'survivor': chosen}
            if hint:
                note_flags.append('Candidate selection is a review hint; inspect all competing records before approving')

        row = {
            'website_no': idx,
            'category': category,
            'facility': s(w.get('name')),
            'crm_account_id': account_id,
            'crm_existing_name': s(chosen.get('name')) if chosen else '',
            'crm_current_parent': s(chosen.get('parent_name')) if chosen else '',
            'crm_current_parent_id': s(chosen.get('parent_id')) if chosen else '',
            'new_parent_id': parent_id if (create_payload is not None or (chosen is not None and s(chosen.get('parent_id')) != parent_id)) else '',
            'website_address': s(w.get('address')),
            'website_city': s(w.get('city')),
            'website_state': s(w.get('state')),
            'website_zip': s(w.get('zip')),
            'website_phone': s(w.get('phone')),
            'crm_phone': s(chosen.get('phone')) if chosen else '',
            'website_care_offerings': '; '.join(offerings(w.get('care_offerings'))),
            'crm_care_type': s(chosen.get('care_type')) if chosen else '',
            'lifetime_revenue': money(chosen.get('lifetime_revenue')) if chosen else 0,
            'outstanding_ar': money(chosen.get('outstanding_ar')) if chosen else 0,
            'operation': operation,
            'field_changes': json.dumps(changes, ensure_ascii=False),
            'exact_actions': ' | '.join(f'{x["field"]}: {x["from"] or "EMPTY"} -> {x["to"]}' for x in changes) if changes else ('CREATE new account' if create_payload else 'No change'),
            'other_candidate_ids': '; '.join(s(a['account_id']) for a in peers),
            'review_flags': ' | '.join(note_flags),
            'source_url': s(w.get('source_url')),
        }
        facility_rows.append(row)
        if category != 'A_MATCH_NO_CHANGE':
            proposals.append({
                'proposal_key': f'website:{norm_text(w.get("state"))}:{norm_text(w.get("city"))}:{norm_address(w.get("address"))}:{category}',
                'source': 'website', 'category': category, 'facility': s(w.get('name')),
                'account_id': account_id or None, 'operation': operation,
                'changes': changes, 'create_payload': create_payload,
                'evidence': {'source_url': s(w.get('source_url')), 'same_street': same_place(w, chosen) if chosen else False,
                             'website_address': s(w.get('address')), 'website_city': s(w.get('city')),
                             'website_state': s(w.get('state')), 'website_zip': s(w.get('zip')),
                             'matched_crm_address': s(chosen.get('billing_street')) if chosen else None,
                             'matched_crm_name': s(chosen.get('name')) if chosen else None,
                             'revenue': money(chosen.get('lifetime_revenue')) if chosen else None,
                             'ar': money(chosen.get('outstanding_ar')) if chosen else None},
                'review_flags': note_flags, 'candidate_ids': [account_id] + [s(a['account_id']) for a in peers] if chosen else [],
                'approval_required': True,
            })

    # Extra CRM accounts: only relevant Bellhaven-owned facilities and same-site
    # competing candidate accounts, NOT unrelated records elsewhere in the 121.
    cleanup = []
    for a in crm:
        aid = s(a.get('account_id'))
        if not aid or aid in primary_ids or aid == parent_id:
            continue
        if aid in web_matches:
            entry = web_matches[aid]
            w, survivor = entry['site'], entry['survivor']
            same_named = norm_name(a.get('name')) == norm_name(survivor.get('name'))
            same_parent = s(a.get('parent_id')) == parent_id and s(survivor.get('parent_id')) == parent_id
            financial = money(a.get('lifetime_revenue')) > 0 and money(a.get('outstanding_ar')) > 0
            if same_named and same_parent and not financial:
                classification = 'DUPLICATE_CONFIDENT'
                action = 'MARK_INACTIVE_DUPLICATE'
                changes = [change('status', s(a.get('status')), 'Inactive'),
                           change('duplicate_of_account', s(a.get('duplicate_of_account')), s(survivor.get('account_id')))]
            else:
                classification = 'CROSS_PARENT_OR_AMBIGUOUS_SAME_ADDRESS'
                action = 'MANUAL_REVIEW'
                changes = []
            reasons = f'Same physical address as website facility {w["name"]}; proposed survivor={survivor["account_id"]}; preserve ownership/billing history until verified'
        elif s(a.get('parent_id')) == parent_id:
            classification = 'NOT_ON_CURRENT_WEBSITE'
            action = 'MARK_NEEDS_REVIEW'
            changes = []
            if s(a.get('status')) != 'Needs Review':
                changes.append(change('status', s(a.get('status')), 'Needs Review'))
            note = f'Not on current Bellhaven website roster; verify closure, divestiture, or rename before changing parent/status. Revenue={money(a.get("lifetime_revenue")):g}; outstanding AR={money(a.get("outstanding_ar")):g}.'
            nc = note_change(a, note)
            if nc: changes.append(nc)
            reasons = 'Account is linked to Bellhaven but no matching facility found on the current website'
        else:
            continue
        if not changes and action == 'MARK_NEEDS_REVIEW':
            continue
        item = {
            'crm_account_id': aid, 'crm_name': s(a.get('name')),
            'classification': classification, 'operation': action,
            'current_parent_id': s(a.get('parent_id')), 'survivor_account_id': s(survivor.get('account_id')) if aid in web_matches else '',
            'lifetime_revenue': money(a.get('lifetime_revenue')), 'outstanding_ar': money(a.get('outstanding_ar')),
            'exact_actions': ' | '.join(f'{c["field"]}: {c["from"] or "EMPTY"} -> {c["to"]}' for c in changes) if changes else 'Manual review; no automatic mutation',
            'changes': json.dumps(changes, ensure_ascii=False), 'evidence': reasons,
        }
        cleanup.append(item)
        if changes:
            proposals.append({
                'proposal_key': f'crm:{aid}:{classification}', 'source': 'crm_cleanup',
                'category': classification, 'account_id': aid, 'facility': s(a.get('name')),
                'operation': action, 'changes': changes, 'create_payload': None,
                'evidence': {'reason': reasons, 'revenue': money(a.get('lifetime_revenue')), 'ar': money(a.get('outstanding_ar'))},
                'approval_required': True,
            })
    return facility_rows, cleanup, proposals


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def write_report(out: Path, website: list[dict], crm: list[dict], facilities: list[dict], cleanup: list[dict], proposals: list[dict]):
    counts = Counter(x['category'] for x in facilities)
    cleanup_counts = Counter(x['classification'] for x in cleanup)
    summary = {
        'website_facility_count': len(website), 'crm_record_count': len(crm),
        'classified_website_facility_count': len(facilities),
        'categories': {cat: counts.get(cat, 0) for cat in CATEGORIES},
        'crm_cleanup_categories': dict(sorted(cleanup_counts.items())),
        'crm_cleanup_total': len(cleanup), 'proposals_with_potential_changes': len(proposals),
        'write_back_performed': False,
    }
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Bellhaven reconciliation report', '',
             f'Website facilities: **{len(website)}** · CRM records: **{len(crm)}**', '',
             'All suggestions require human review. No CRM updates were performed.', '']
    for category in CATEGORIES:
        group = [x for x in facilities if x['category'] == category]
        lines += [f'## {category} ({len(group)})', '']
        for r in group:
            lines.append(f'- **{r["facility"]}** — CRM `{r["crm_account_id"] or "<CREATE>"}`; {r["exact_actions"]}')
            if r['review_flags']:
                lines.append(f'  - Review: {r["review_flags"]}')
        lines.append('')
    lines += [f'## CRM cleanup ({len(cleanup)})', '']
    for r in cleanup:
        lines.append(f'- **{r["crm_name"]}** `{r["crm_account_id"]}` — {r["classification"]}: {r["exact_actions"]}')
    (out / 'reconcile_report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (out / 'review_proposals.json').write_text(json.dumps(proposals, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary


def main():
    ap = argparse.ArgumentParser(description='Bellhaven reconciliation (READ ONLY)')
    ap.add_argument('--website', default=DEFAULT_WEBSITE_FILE, help=f'Website JSON/CSV (default: {DEFAULT_WEBSITE_FILE})')
    ap.add_argument('--crm', default=DEFAULT_CRM_FILE, help=f'CRM JSON/CSV (default: {DEFAULT_CRM_FILE})')
    ap.add_argument('--out', default='reconcile_output', help='output folder')
    ap.add_argument('--parent-id', default=DEFAULT_PARENT_ID)
    args = ap.parse_args()
    try:
        website, crm = load_records(args.website), load_records(args.crm)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        ap.error(str(exc))
    for label, records, required in [
        ('scraped locations', website, ('name', 'address', 'city', 'state')),
        ('CRM snapshot', crm, ('account_id', 'name', 'parent_id', 'billing_street')),
    ]:
        if not records:
            ap.error(f'{label} file is empty')
        if not isinstance(records[0], dict):
            ap.error(f'{label}: expected an array of JSON objects')
        missing = set(required) - set(records[0])
        if missing:
            ap.error(f'{label}: missing required keys: {sorted(missing)}')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    facilities, cleanup, proposals = reconcile(website, crm, args.parent_id)
    write_csv(out / 'facilities_reconciliation.csv', facilities,
              ['website_no', 'category', 'facility', 'crm_account_id', 'crm_existing_name',
               'crm_current_parent', 'crm_current_parent_id', 'new_parent_id',
               'website_address', 'website_city', 'website_state', 'website_zip',
               'website_phone', 'crm_phone', 'website_care_offerings', 'crm_care_type',
               'lifetime_revenue', 'outstanding_ar', 'operation', 'exact_actions',
               'field_changes', 'other_candidate_ids', 'review_flags', 'source_url'])
    write_csv(out / 'crm_cleanup.csv', cleanup,
              ['crm_account_id', 'crm_name', 'classification', 'operation', 'current_parent_id',
               'survivor_account_id', 'lifetime_revenue', 'outstanding_ar', 'exact_actions', 'changes', 'evidence'])
    summary = write_report(out, website, crm, facilities, cleanup, proposals)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('Output folder:', out.resolve())


if __name__ == '__main__':
    main()
