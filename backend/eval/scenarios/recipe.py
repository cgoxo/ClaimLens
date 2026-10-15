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
    # what the forgeries changed (set by forgeries.apply)
    shown_total: int | None = None  # a retyped hospital total
    shown_item: tuple | None = None  # (index into items, retyped amount)
    extra_claim_pages: int = 0
    _stay: int = 3  # nights charged on the bill (the genuine stay)

    @property
    def days(self) -> int:
        return self._stay

    @property
    def items(self) -> list:
        return [(f"Room charges ({self._stay} days x Rs {self.room_rate:,})", self._stay * self.room_rate),
                *self.other_items]

    @property
    def hospital_total(self) -> int:
        return sum(a for _, a in self.items)

    def copy(self, **changes) -> "Recipe":
        return replace(self, **changes)


def money(n: int) -> str:
    return f"Rs {n:,}"


def day(d: date) -> str:
    return d.strftime("%d-%b-%Y")


def make_recipe(seed: int, run: str) -> Recipe:
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
    r.claimed = r.hospital_total + sum(p.amount for p in pharmacies)
    return r
