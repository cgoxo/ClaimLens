"""A random but self-consistent claim: the person, the stay, the bills and the policy it's claimed against."""

from dataclasses import dataclass, field, replace
from datetime import date, timedelta

import numpy as np

FIRST = ["Rahul", "Asha", "Vikram", "Meera", "Arjun", "Kavya", "Rohan", "Neha", "Imran", "Divya"]
LAST = ["Verma", "Iyer", "Shahani", "Nair", "Reddy", "Kapoor", "Dasgupta", "Menon", "Khanna", "Joshi"]
HOSPITALS = ["Sunrise Eye & General Hospital, Pune", "Lotus Multispeciality Hospital, Nagpur",
             "Green Valley Hospital, Indore", "City Care Hospital, Surat"]
# condition, procedure, on the policy's 24-month waiting list?
CONDITIONS = [("Cataract", "Phacoemulsification with IOL implant", True),
              ("Hernia", "Laparoscopic hernia repair", True),
              ("Appendicitis", "Laparoscopic appendectomy", False),
              ("Dengue fever", "Supportive inpatient care", False),
              ("Forearm fracture", "Open reduction internal fixation", False)]
WAITING_LIST = ["Cataract", "Hernia", "Knee replacement", "Kidney stones"]
# bill items on the standard non-payable list (the policy may or may not carry the clause)
STANDARD_CONSUMABLES = ["Gloves", "Face mask", "Admission kit", "Registration charges", "Toiletries",
                        "Cotton and dressing material"]


@dataclass
class Pharmacy:
    invoice: str
    day: date
    amount: int
    inpatient: bool = True


@dataclass
class Recipe:
    run: str
    seed: int
    patient: str
    names: dict = field(default_factory=dict)  # page title -> name printed there (default: patient)
    hospital: str = ""
    policy_no: str = ""
    policy_no_on_claim: str = ""
    start: date = date(2023, 1, 1)
    admission: date = date(2026, 3, 10)
    discharge: date = date(2026, 3, 13)
    procedure_day: date = date(2026, 3, 11)
    condition: str = ""
    procedure: str = ""
    room_rate: int = 3000
    room_limit: int | None = None
    other_items: list = field(default_factory=list)  # (description, amount)
    invoice: str = ""
    bill_day: date = date(2026, 3, 13)
    pharmacies: list = field(default_factory=list)
    claimed: int = 0
    claim_day: date = date(2026, 3, 22)
    sum_insured: int = 300000
    # policy rules (all off by default)
    co_pay: float = 0  # percent
    co_pay_age: int | None = None  # the co-pay applies only above this age
    deductible: int = 0
    sub_limit: int | None = None  # rupees, for the claim's own condition
    icu_limit_pct: float | None = None  # percent of the sum insured per day
    proportionate: bool = False
    non_payable_standard: bool = False  # the policy carries the standard non-payable clause
    pre_days: int | None = None  # the cover window (both or neither)
    post_days: int | None = None
    # on the bill
    icu_days: int = 0
    icu_rate: int = 0
    consumables: list = field(default_factory=list)  # (description, amount) of standard non-payable items
    unrelated_item: tuple | None = None  # (description, amount) that does not fit the treatment
    extra_room_days: int = 0  # room days charged beyond the stay
    duplicate_line: bool = False  # the first other item is charged twice
    patient_age: int | None = None
    # what the forgeries changed (set by forgeries.apply)
    shown_total: int | None = None  # a retyped hospital total
    shown_item: tuple | None = None  # (index into items, retyped amount)
    extra_claim_pages: int = 0
    _stay: int = 3  # nights charged on the bill (the genuine stay)

    @property
    def days(self) -> int:
        """Room days charged: the stay less ICU days, plus any extra."""
        return self._stay - self.icu_days + self.extra_room_days

    @property
    def items(self) -> list:
        others = list(self.other_items)
        if self.duplicate_line and others:
            others.insert(1, others[0])
        icu = [(f"ICU charges ({self.icu_days} days x Rs {self.icu_rate:,})", self.icu_days * self.icu_rate)] \
            if self.icu_days else []
        return [(f"Room charges ({self.days} days x Rs {self.room_rate:,})", self.days * self.room_rate),
                *icu, *others, *self.consumables, *([self.unrelated_item] if self.unrelated_item else [])]

    @property
    def hospital_total(self) -> int:
        return sum(a for _, a in self.items)

    def copy(self, **changes) -> "Recipe":
        return replace(self, **changes)


def money(n: int) -> str:
    return f"Rs {n:,}"


def day(d: date) -> str:
    return d.strftime("%d-%b-%Y")


def make_recipe(seed: int, run: str, rules: bool = True) -> Recipe:
    """`rules` False: the plain claim of a seed, with no policy rules or extra bill lines."""
    rng = np.random.default_rng(seed)
    patient = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    condition, procedure, _ = CONDITIONS[int(rng.integers(0, len(CONDITIONS)))]
    admission = date(2026, 1, 5) + timedelta(days=int(rng.integers(0, 200)))
    stay = int(rng.integers(2, 6))
    sum_insured = int(rng.choice([300000, 500000, 1000000]))
    limit = sum_insured // 100 if rng.random() < 0.6 else None
    rate = int(round((limit * rng.uniform(0.5, 0.95) if limit else rng.uniform(2000, 6000)) / 100) * 100)
    others = [(d, int(rng.integers(5, 300)) * 100) for d in
              rng.choice(["Surgeon and OT charges", "Anaesthesia", "Consumables", "Medicines", "Lab tests",
                          "Nursing charges"], size=int(rng.integers(2, 5)), replace=False)]
    discharge = admission + timedelta(days=stay)
    pharmacies = [Pharmacy(f"PH-{run}-{seed}-{k}", admission + timedelta(days=int(rng.integers(0, stay + 1))),
                           int(rng.integers(5, 80)) * 100) for k in range(int(rng.integers(0, 3)))]
    r = Recipe(run=run, seed=seed, patient=patient, _stay=stay, hospital=str(rng.choice(HOSPITALS)),
               policy_no=f"EH-2025-{int(rng.integers(100000, 999999))}", start=admission - timedelta(days=int(rng.integers(760, 1100))),
               admission=admission, discharge=discharge, procedure_day=admission + timedelta(days=1),
               condition=condition, procedure=procedure, room_rate=rate, room_limit=limit,
               other_items=[(str(d), a) for d, a in others], invoice=f"INV-{run}-{seed}",
               bill_day=discharge, pharmacies=pharmacies, claim_day=discharge + timedelta(days=int(rng.integers(5, 15))),
               sum_insured=sum_insured)
    r.policy_no_on_claim = r.policy_no
    if rules:
        _add_rules(r, np.random.default_rng([seed, 17]))  # its own stream: the fields above never change
    r.claimed = r.hospital_total + sum(p.amount for p in pharmacies)
    return r


def _add_rules(r: Recipe, x: np.random.Generator) -> None:
    """Mix in policy rules and bill lines. Every draw is made whether or not it is used, so one choice never
    shifts the next."""
    stay, si = r._stay, r.sum_insured
    icu, pct, over, under = x.random() < 0.3, float(x.choice([2, 3])), x.random() < 0.5, x.uniform(0.6, 0.95)
    icu_days, above = int(x.integers(1, stay)), x.uniform(1.1, 1.6)
    if icu:
        limit = si * pct / 100
        r.icu_limit_pct, r.icu_days = pct, icu_days
        r.icu_rate = int(round(limit * (above if over else under) / 100) * 100)
    deductible, d_on = int(x.choice([10000, 25000])), x.random() < 0.3
    cp_on, cp_pct, by_age, roll = x.random() < 0.3, float(x.choice([10, 20])), x.random() < 0.4, x.random()
    over_age, under_age, any_age, age_known = (int(x.integers(61, 80)), int(x.integers(25, 61)),
                                               int(x.integers(20, 75)), x.random() < 0.7)
    sub_on, sub_factor = x.random() < 0.25, x.uniform(0.4, 1.4)
    prop, np_on, cons_on = x.random() < 0.4, x.random() < 0.4, x.random() < 0.5
    k = int(x.integers(1, 4))
    cons = [(str(c), int(x.integers(1, 26)) * 100) for c in x.choice(STANDARD_CONSUMABLES, size=k, replace=False)]
    win_on, pre, post = x.random() < 0.3, int(x.choice([30, 60])), int(x.choice([30, 60, 90]))
    out_on, early, gap, amount = x.random() < 0.6, x.random() < 0.7, int(x.integers(3, 20)), int(x.integers(3, 20)) * 100

    if d_on:
        r.deductible = deductible
    if cp_on:
        r.co_pay = cp_pct
        if by_age:
            r.co_pay_age = 60
            r.patient_age = over_age if roll < 0.45 else under_age if roll < 0.85 else None
        elif age_known:
            r.patient_age = any_age
    elif age_known:
        r.patient_age = any_age
    r.proportionate, r.non_payable_standard = prop, np_on
    if cons_on:
        r.consumables = cons
    if win_on:
        r.pre_days, r.post_days = pre, post
        if out_on:
            if early:
                when = r.admission - timedelta(days=pre + gap)
            else:
                when = r.discharge + timedelta(days=post + gap)
                r.claim_day = when + timedelta(days=2)
            r.pharmacies = [*r.pharmacies, Pharmacy(f"PH-{r.run}-{r.seed}-w", when, amount, inpatient=False)]
    if sub_on:
        r.sub_limit = max(5000, int(round(r.hospital_total * sub_factor / 1000)) * 1000)
