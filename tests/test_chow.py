"""Verify CHOW vs direct reparent, and executor refuses unsafe parent updates."""
import pytest
import match
import apply_proposals as executor

PARENT = match.DEFAULT_PARENT_ID


def fixture(revenue, ar):
    web = [{'name': 'Bellhaven of Tiffin', 'address': '45 St Lawrence Dr',
            'city': 'Tiffin', 'state': 'OH', 'zip': '44883',
            'phone': '555-000-0000', 'care_offerings': ['Short-Term Rehabilitation & Nursing']}]
    old = {'account_id': 'old_tiffin', 'name': 'Bellhaven of Tiffin',
           'parent_id': 'CEDAR', 'billing_street': '45 St Lawrence Dr',
           'billing_city': 'Tiffin', 'billing_state': 'OH', 'billing_zip': '44883',
           'care_type': 'Skilled Nursing', 'phone': '555-000-0000', 'status': 'Active',
           'lifetime_revenue': revenue, 'outstanding_ar': ar,
           'chow_current_account': '', 'note': ''}
    return web, old


@pytest.mark.parametrize('revenue,ar,operation', [
    (0, 0, 'UPDATE'),
    (50000, 0, 'UPDATE'),
    (0, 5000, 'UPDATE'),
    (50000, 5000, 'CHOW'),
])
def test_financial_rule(revenue, ar, operation):
    web, old = fixture(revenue, ar)
    rows, _, proposals = match.reconcile(web, [old], PARENT)
    assert proposals[0]['operation'] == operation
    if operation == 'CHOW':
        assert rows[0]['category'] == 'D_CHOW_CREATE_AND_LINK'
        assert proposals[0]['create_payload']['parent_id'] == PARENT
        assert {c['field'] for c in proposals[0]['changes']} == {'chow_current_account'}
    else:
        assert any(c['field'] == 'parent_id' and c['to'] == PARENT for c in proposals[0]['changes'])


def test_executor_refuses_chow_when_financial_condition_no_longer_holds():
    with pytest.raises(RuntimeError, match='CHOW condition no longer holds'):
        executor.validate_financial_chow({'lifetime_revenue': 50000, 'outstanding_ar': 0, 'parent_id': 'CEDAR'}, PARENT)


def test_executor_blocks_direct_reparent_when_ar_is_outstanding(tmp_path, monkeypatch):
    monkeypatch.setattr(executor, 'EXECUTION_FILE', tmp_path / 'execution_states.json')
    web, old = fixture(0, 0)
    proposal = match.reconcile(web, [old], PARENT)[2][0]

    class FakeClient:
        def get(self, aid):
            return {**old, 'lifetime_revenue': 50000, 'outstanding_ar': 5000}
        def patch(self, *args):
            raise AssertionError('Must not write')

    with pytest.raises(RuntimeError, match='must use CHOW'):
        executor.execute_one(proposal, FakeClient(), {})
