"""Cards: the two upload forms, claim and policy. Each card's files, in order, form its stream of pages."""

import re

from claimlens.models import Card, Case, CaseFile

CARD_ID = re.compile(r"^[a-z0-9-]{1,32}$")
LABELS = {"claim": "Claim", "policy": "Policy"}


def cards_of(case: Case) -> list[Card]:
    """The case's cards; a case from before cards becomes one claim card and one policy card."""
    if case.cards:
        return case.cards
    return [Card(id=doc, role=doc, files=[CaseFile(key=key, name=key.rsplit("/", 1)[-1])])
            for doc, key in case.files.items() if doc in LABELS]


def stream_of(card: Card) -> str:
    return card.role


def ordered(cards: list[Card], stream: str) -> list[Card]:
    return [c for c in cards if stream_of(c) == stream]


def card_label(cards: list[Card], card_id: str) -> str:
    card = next((c for c in cards if c.id == card_id), None)
    return LABELS[card.role] if card else card_id


def layout_error(cards: list[Card], settings) -> str | None:
    """What is wrong with this set of cards, or None. A case is exactly one claim card and one policy card."""
    ids = [c.id for c in cards]
    if bad := next((i for i in ids if not CARD_ID.match(i)), None):
        return f"card id {bad!r} must be 1-32 lower-case letters, digits or hyphens"
    if len(set(ids)) != len(ids):
        return "duplicate card id"
    roles = [c.role for c in cards]
    if roles.count("claim") != 1:
        return "exactly one claim card"
    if roles.count("policy") != 1:
        return "exactly one policy card"
    return None
