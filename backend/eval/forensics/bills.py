"""Fictional one-page hospital bills, drawn straight to an image so every field's box is known exactly."""

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1654, 2339  # A4 at 200 dpi
PAPER = (246, 244, 238)
INK = (32, 32, 38)
FIRST = ["Rahul", "Asha", "Vikram", "Meera", "Arjun", "Kavya", "Rohan", "Neha", "Imran", "Divya"]
LAST = ["Verma", "Iyer", "Shah", "Nair", "Reddy", "Kapoor", "Das", "Menon", "Khan", "Joshi"]
ITEMS = ["Room charges", "Surgeon fees", "OT charges", "Anaesthesia", "Medicines", "Consumables",
         "Lab tests", "Nursing", "Radiology", "Physiotherapy"]


@dataclass
class Field:
    name: str
    kind: str  # amount, date, invoice or text
    box: tuple[float, float, float, float]
    value: str
    edited: bool = False


@dataclass
class Bill:
    png: bytes
    fields: list[Field] = field(default_factory=list)
    items: list[tuple[str, int]] = field(default_factory=list)  # (field name, amount) for each line item
    total_field: str = "total"


def money(n: int) -> str:
    return f"Rs {n:,}"


def render_bill(seed: int) -> Bill:
    """One bill. The seed picks the people, the items and the look: bold total, stamp, handwriting, highlighter."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    big, body, small = (ImageFont.load_default(size=s) for s in (46, 30, 24))
    bill = Bill(png=b"")

    def text(xy, value, font, name=None, kind="text", fill=INK):
        d.text(xy, value, fill=fill, font=font)
        if name:
            bill.fields.append(Field(name, kind, tuple(map(float, d.textbbox(xy, value, font=font))), value))

    text((120, 110), f"{rng.choice(['Sunrise', 'Lotus', 'Green Valley', 'City Care'])} Hospital", big)
    text((120, 180), "FICTIONAL SAMPLE FOR TESTING", small)
    text((120, 260), "Invoice:", body)
    text((330, 260), f"INV-{seed:05d}-{int(rng.integers(1000, 9999))}", body, "invoice", "invoice")
    text((120, 310), "Bill date:", body)
    day, month = int(rng.integers(1, 28)), rng.choice(["Jan", "Feb", "Mar", "Apr", "May", "Jun"])
    text((330, 310), f"{day:02d}-{month}-2026", body, "date", "date")
    text((120, 360), "Patient:", body)
    text((330, 360), f"{rng.choice(FIRST)} {rng.choice(LAST)}", body, "patient")
    names = list(rng.choice(ITEMS, size=int(rng.integers(4, 8)), replace=False))
    y, total = 480, 0
    for i, name in enumerate(names):
        amount = int(rng.integers(5, 400)) * 100
        total += amount
        text((120, y), name, body)
        text((1180, y), money(amount), body, f"item{i}", "amount")
        bill.items.append((f"item{i}", amount))
        y += 60
    bold = bool(rng.random() < 0.4)
    font = ImageFont.load_default(size=36) if bold else body
    text((120, y + 40), "TOTAL", font)
    text((1180, y + 40), money(total), font, "total", "amount")
    if rng.random() < 0.3:  # a rubber stamp over an amount
        x0, y0 = 1120, 470 + 60 * int(rng.integers(0, len(names)))
        d.ellipse((x0, y0 - 40, x0 + 260, y0 + 120), outline=(160, 40, 50), width=6)
        d.text((x0 + 50, y0 + 20), "PAID", fill=(160, 40, 50), font=big)
    if rng.random() < 0.3:  # a handwritten note
        pts = [(700 + 9 * i, 1900 + 18 * np.sin(i / 2.0) + rng.normal(0, 3)) for i in range(60)]
        d.line(pts, fill=(30, 50, 140), width=4)
    if rng.random() < 0.3:  # a highlighter pass over a line
        over = Image.new("RGBA", img.size, (0, 0, 0, 0))
        hy = 470 + 60 * int(rng.integers(0, len(names)))
        ImageDraw.Draw(over).rectangle((110, hy, 1500, hy + 44), fill=(250, 235, 60, 90))
        img = Image.alpha_composite(img.convert("RGBA"), over).convert("RGB")
    out = io.BytesIO()
    img.save(out, "PNG")
    bill.png = out.getvalue()
    return bill
