"""Each forgery changes the recipe (what the documents say) and may also be applied to the files (render.py)."""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

import numpy as np

from eval.scenarios.recipe import LAST, Recipe


@dataclass
class Forgery:
    apply: Callable[[Recipe], Recipe] = lambda r: r
    conflicts: set = field(default_factory=set)
    rejection: bool = False
    needs: Callable[[Recipe], bool] = lambda r: True


def _retype_total(r: Recipe) -> Recipe:
    delta = 3000
    return r.copy(shown_total=r.hospital_total + delta, claimed=r.claimed + delta)  # and claims the inflated total


def _retype_line(r: Recipe) -> Recipe:
    return r.copy(shown_item=(len(r.items) - 1, r.items[-1][1] + 2500))


def _typo(name: str) -> str:
    first, last = name.split(" ", 1)
    return f"{first} {last[:1]}{'a' if last[1] != 'a' else 'e'}{last[2:]}"


def _admit_after_discharge(r: Recipe) -> Recipe:
    # the printed discharge is before the admission (the stay and the bills are unchanged)
    return r.copy(discharge=r.admission - timedelta(days=2))


def _wrong_policy(r: Recipe) -> Recipe:
    return r.copy(policy_no_on_claim="EH-2024-" + str(int(r.policy_no[-6:]) + 111111)[-6:])


def _waiting(r: Recipe) -> Recipe:
    from eval.scenarios.recipe import CONDITIONS

    condition, procedure, _ = next(c for c in CONDITIONS if c[2])
    return r.copy(condition=condition, procedure=procedure, start=r.admission - timedelta(days=365))


def _room_over(r: Recipe) -> Recipe:
    rate = r.room_limit + 1500
    old = r.items[0][1]
    return r.copy(room_rate=rate, claimed=r.claimed - old + rate * r.days)


def _missing(r: Recipe) -> Recipe:
    return r  # the files lose a page; the claim form still claims it


def _pharmacy_after(r: Recipe) -> Recipe:
    from eval.scenarios.render import pharmacy_after

    return pharmacy_after(r)


TAMPER = {"retype_total", "retype_line", "editor_resave", "late_edit"}
REJECT = {"cv_in_claim", "bill_in_policy", "policy_in_claim"}
CLAIMED = {"retype_total", "claimed_mismatch", "missing_page"}

FORGERIES: dict[str, Forgery] = {
    "retype_total": Forgery(_retype_total),
    "retype_line": Forgery(_retype_line),
    "editor_resave": Forgery(),
    "late_edit": Forgery(),
    "incremental_save": Forgery(),
    "pharmacy_after_discharge": Forgery(_pharmacy_after, {"admit_after_discharge"}),
    "admit_after_discharge": Forgery(_admit_after_discharge, {"pharmacy_after_discharge"}),
    "name_typo": Forgery(lambda r: r.copy(names={"Discharge Summary": _typo(r.patient)}), {"different_name"}),
    "different_name": Forgery(lambda r: r.copy(names={"Discharge Summary": f"Suresh {LAST[(LAST.index(r.patient.split()[1]) + 3) % len(LAST)]}"}),
                              {"name_typo"}),
    "claimed_mismatch": Forgery(lambda r: r.copy(claimed=int(r.claimed * 1.2) // 100 * 100)),
    "reused_invoice": Forgery(),
    "wrong_policy_number": Forgery(_wrong_policy),
    "waiting_period": Forgery(_waiting),
    "room_over_limit": Forgery(_room_over, needs=lambda r: r.room_limit is not None),
    "duplicate_page": Forgery(conflicts={"missing_page"}),
    "missing_page": Forgery(_missing, {"duplicate_page"}, needs=lambda r: len(r.pharmacies) > 0),
    "cv_in_claim": Forgery(rejection=True),
    "bill_in_policy": Forgery(rejection=True),
    "policy_in_claim": Forgery(rejection=True),
}
for name, f in FORGERIES.items():  # one tamper at a time; one claimed-amount change at a time; rejections alone
    if name in TAMPER:
        f.conflicts |= TAMPER - {name}
    if name in CLAIMED:
        f.conflicts |= CLAIMED - {name}
    if name in REJECT:
        f.conflicts |= set(FORGERIES) - {name}
    else:
        f.conflicts |= REJECT


def pick(rng: np.random.Generator, recipe: Recipe | None = None) -> list[str]:
    """0–3 compatible forgeries; a quarter of cases are clean."""
    if rng.random() < 0.25:
        return []
    names = [n for n in FORGERIES if not FORGERIES[n].rejection]
    if rng.random() < 0.08:
        return [str(rng.choice(sorted(REJECT)))]
    chosen: list[str] = []
    for n in rng.permutation(names)[: int(rng.integers(1, 4)) * 3]:
        f = FORGERIES[str(n)]
        if len(chosen) < 3 and not (f.conflicts & set(chosen)) and (recipe is None or f.needs(recipe)):
            chosen.append(str(n))
    return chosen
