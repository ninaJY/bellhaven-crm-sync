"""Test the user's real match.py reconciliation functions without network access."""
import match

PARENT = match.DEFAULT_PARENT_ID


def website(name='Bellhaven of Zanesville', address='2680 Maple Ave', city='Zanesville', state='OH', zip_code='43701'):
    return {'name': name, 'address': address, 'city': city, 'state': state,
            'zip': zip_code, 'phone': '(555) 123-4567',
            'care_offerings': ['Short-Term Rehabilitation & Nursing'], 'source_url': 'https://example.test/facility'}


def account(name='Bellhaven of Zanesville', street='2680 Maple Avenue', parent=PARENT, revenue=0, ar=0, aid='crm001'):
    return {'account_id': aid, 'name': name, 'parent_id': parent,
            'billing_street': street, 'billing_city': 'Zanesville',
            'billing_state': 'OH', 'billing_zip': '43701',
            'phone': '(555) 123-4567', 'care_type': 'Skilled Nursing',
            'status': 'Active', 'lifetime_revenue': revenue,
            'outstanding_ar': ar, 'note': ''}


def test_same_address_different_abbreviation_no_change():
    rows, cleanup, proposals = match.reconcile([website()], [account()], PARENT)
    assert rows[0]['category'] == 'A_MATCH_NO_CHANGE'
    assert rows[0]['crm_account_id'] == 'crm001'
    assert not proposals


def test_rebrand_same_address_reparent():
    rows, cleanup, proposals = match.reconcile(
        [website()], [account(name='Cedar Trail of Zanesville', parent='OTHER')], PARENT
    )
    assert rows[0]['category'] == 'E_RENAME_OR_REPARENT'
    assert proposals[0]['operation'] == 'UPDATE'
    patch = {c['field']: c['to'] for c in proposals[0]['changes']}
    assert patch['parent_id'] == PARENT
    assert patch['name'] == 'Bellhaven of Zanesville'


def test_same_name_different_city_not_automatically_matched():
    a = account()
    a['billing_city'] = 'Columbus'
    rows, _, proposals = match.reconcile([website()], [a], PARENT)
    assert rows[0]['category'] == 'F_CREATE_NEW'
    assert proposals[0]['operation'] == 'CREATE'


def test_stale_zip_still_matched_and_proposed_fix():
    a = account()
    a['billing_zip'] = '99999'
    rows, _, proposals = match.reconcile([website()], [a], PARENT)
    assert rows[0]['category'] == 'B_MINOR_FIELD_UPDATE'
    assert {'field': 'billing_zip', 'from': '99999', 'to': '43701'} in proposals[0]['changes']
