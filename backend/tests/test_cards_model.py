import pytest

from claimlens.cards import card_label, cards_of, layout_error, ordered
from claimlens.models import Card, Case


def test_cards_of_old_case():
    case = Case(id="x", owner_email="a@x.com", files={"claim": "cases/x/claim.pdf", "policy": "cases/x/policy.pdf"})
    cards = cards_of(case)
    assert [(c.id, c.role) for c in cards] == [("claim", "claim"), ("policy", "policy")]
    assert cards[0].files[0].key == "cases/x/claim.pdf" and cards[0].files[0].name == "claim.pdf"


def test_cards_of_new_case_keeps_cards():
    cards = [Card(id="claim", role="claim"), Card(id="policy", role="policy")]
    assert cards_of(Case(id="x", owner_email="a@x.com", cards=cards)) == cards


def test_streams_and_labels():
    cards = [Card(id="policy", role="policy"), Card(id="claim", role="claim")]
    assert [c.id for c in ordered(cards, "claim")] == ["claim"]
    assert [c.id for c in ordered(cards, "policy")] == ["policy"]
    assert [card_label(cards, c.id) for c in cards] == ["Policy", "Claim"]


@pytest.mark.parametrize("cards, message", [
    ([Card(id="claim", role="claim")], "exactly one policy card"),
    ([Card(id="policy", role="policy")], "exactly one claim card"),
    ([Card(id="c1", role="claim"), Card(id="c2", role="claim"), Card(id="policy", role="policy")],
     "exactly one claim card"),
    ([Card(id="Bad Id", role="claim"), Card(id="policy", role="policy")], "card id"),
    ([Card(id="x", role="claim"), Card(id="x", role="policy")], "duplicate card id"),
    ([Card(id="claim", role="claim"), Card(id="policy", role="policy")], None),
])
def test_layout_errors(settings, cards, message):
    error = layout_error(cards, settings)
    assert error == message if message is None else message in error


def test_bill_role_is_gone():
    with pytest.raises(ValueError):
        Card(id="b1", role="bill")
