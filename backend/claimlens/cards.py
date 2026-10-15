"""Cards: the user's grouping of uploaded files. Pages of the claim-side cards form the claim stream."""

import re

from claimlens.models import Card, Case, CaseFile

CARD_ID = re.compile(r"^[a-z0-9-]{1,32}$")
CLAIM_ORDER = {"claim_form": 0, "bill": 1, "supporting": 2}


def cards_of(case: Case) -> list[Card]:
    """The case's cards; a case from before cards becomes one claim-form card and one policy card."""
    if case.cards:
        return case.cards
    role = {"claim": "claim_form", "policy": "policy"}
    return [Card(id=doc, role=role[doc], files=[CaseFile(key=key, name=key.rsplit("/", 1)[-1])])
            for doc, key in case.files.items() if doc in role]


def stream_of(card: Card) -> str:
    return "policy" if card.role == "policy" else "claim"


def ordered(cards: list[Card], stream: str) -> list[Card]:
    """A stream's cards in page order: claim form, bills (as added), supporting documents."""
    mine = [c for c in cards if stream_of(c) == stream]
    return sorted(mine, key=lambda c: CLAIM_ORDER.get(c.role, 0))  # stable: bills keep their order


def card_label(cards: list[Card], card_id: str) -> str:
    card = next((c for c in cards if c.id == card_id), None)
    if card is None:
        return card_id
    if card.role == "bill":
        n = [c.id for c in cards if c.role == "bill"].index(card_id) + 1
        return f"Bill {n} · {card.kind}"
    return {"claim_form": "Claim form", "supporting": "Supporting documents", "policy": "Policy"}[card.role]


def layout_error(cards: list[Card], settings) -> str | None:
    """What is wrong with this set of cards, or None."""
    ids = [c.id for c in cards]
    if bad := next((i for i in ids if not CARD_ID.match(i)), None):
        return f"card id {bad!r} must be 1-32 lower-case letters, digits or hyphens"
    if len(set(ids)) != len(ids):
        return "duplicate card id"
    roles = [c.role for c in cards]
    if roles.count("policy") != 1:
        return "exactly one policy card"
    if roles.count("claim_form") > 1:
        return "at most one claim form card"
    if roles.count("supporting") > 1:
        return "at most one supporting documents card"
    if roles.count("bill") > settings.max_bill_cards:
        return f"at most {settings.max_bill_cards} bills"
    if bill := next((c for c in cards if c.role == "bill" and not c.kind), None):
        return f"bill {bill.id} needs a kind"
    return None
