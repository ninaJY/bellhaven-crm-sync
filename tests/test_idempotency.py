"""Use an in-memory fake CRM; no real POST, PATCH or network calls."""
import copy
import match
import apply_proposals as executor

PARENT = match.DEFAULT_PARENT_ID


def site():
    return {'name': 'Bellhaven of Batavia', 'address': '2000 Hospital Dr',
            'city': 'Batavia', 'state': 'OH', 'zip': '45103', 'phone': '555-222-3333',
            'care_offerings': ['Short-Term Rehabilitation & Nursing']}


class FakeCRM:
    def __init__(self, initial=None):
        self.accounts = {a['account_id']: copy.deepcopy(a) for a in (initial or [])}
        self.post_count = 0
        self.patch_count = 0

    def list_accounts(self):
        return list(self.accounts.values())

    def get(self, aid):
        return copy.deepcopy(self.accounts[aid])

    def create(self, payload):
        self.post_count += 1
        aid = f'created_{self.post_count}'
        self.accounts[aid] = {'account_id': aid, **copy.deepcopy(payload),
                              'lifetime_revenue': 0, 'outstanding_ar': 0,
                              'chow_current_account': ''}
        return aid

    def patch(self, aid, payload):
        self.patch_count += 1
        self.accounts[aid].update(payload)
        return copy.deepcopy(self.accounts[aid])


def test_create_is_not_repeated_when_executor_runs_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(executor, 'EXECUTION_FILE', tmp_path / 'execution_states.json')
    proposal = match.reconcile([site()], [], PARENT)[2][0]
    assert proposal['operation'] == 'CREATE'
    fake = FakeCRM()
    journal = {}
    assert executor.execute_one(proposal, fake, journal) == 'applied'
    assert executor.execute_one(proposal, fake, journal) == 'skipped'
    assert fake.post_count == 1
    assert journal[proposal['proposal_key']]['status'] == 'applied'


def test_chow_second_execution_keeps_original_parent_and_single_successor(tmp_path, monkeypatch):
    monkeypatch.setattr(executor, 'EXECUTION_FILE', tmp_path / 'execution_states.json')
    web = [{**site(), 'name': 'Bellhaven of Tiffin', 'address': '45 St Lawrence Dr',
            'city': 'Tiffin', 'zip': '44883'}]
    old = {'account_id': 'old_tiffin', 'name': 'Bellhaven of Tiffin',
           'billing_street': '45 St Lawrence Dr', 'billing_city': 'Tiffin',
           'billing_state': 'OH', 'billing_zip': '44883',
           'parent_id': 'CEDAR', 'lifetime_revenue': 84000,
           'outstanding_ar': 12400, 'chow_current_account': '',
           'status': 'Active', 'phone': '555-222-3333', 'care_type': 'Skilled Nursing'}
    proposal = match.reconcile(web, [old], PARENT)[2][0]
    assert proposal['operation'] == 'CHOW'
    fake, journal = FakeCRM([old]), {}
    assert executor.execute_one(proposal, fake, journal) == 'applied'
    assert executor.execute_one(proposal, fake, journal) == 'skipped'
    assert fake.post_count == 1
    assert fake.patch_count == 1
    assert fake.get('old_tiffin')['parent_id'] == 'CEDAR'
    assert fake.get('old_tiffin')['lifetime_revenue'] == 84000
    assert fake.get('old_tiffin')['outstanding_ar'] == 12400
    assert fake.get('old_tiffin')['chow_current_account'] == 'created_1'


def test_approved_signature_changes_require_reapproval():
    proposal = match.reconcile([site()], [], PARENT)[2][0]
    state = {proposal['proposal_key']: {'decision': 'approved', 'signature': executor.signature(proposal)}}
    assert executor.approved(proposal, state)
    changed = copy.deepcopy(proposal)
    changed['create_payload']['billing_zip'] = '00000'
    assert not executor.approved(changed, state)
