"""Generate synthetic sample documents for the demo pipeline.

Usage: python scripts/make_samples.py [--output-dir samples]
"""

import argparse
import os
from io import BytesIO

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")


def _draw_invoice(c, items, subtotal, tax, total, currency="USD"):
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1 * inch, 10 * inch, "INVOICE")

    c.setFont("Helvetica", 11)
    c.drawString(1 * inch, 9.5 * inch, f"Invoice No: INV-2026-{hash(str(items)) % 1000:03d}")
    c.drawString(1 * inch, 9.2 * inch, "Date: July 1, 2026")
    c.drawString(1 * inch, 8.9 * inch, "Due Date: July 31, 2026")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * inch, 8.3 * inch, "Bill To:")
    c.setFont("Helvetica", 11)
    c.drawString(1 * inch, 8.0 * inch, "Acme Corp")
    c.drawString(1 * inch, 7.7 * inch, "123 Business Ave, Suite 400")
    c.drawString(1 * inch, 7.4 * inch, "New York, NY 10001")

    y = 6.5 * inch
    c.setFont("Helvetica-Bold", 10)
    c.drawString(1 * inch, y, "Description")
    c.drawString(4 * inch, y, "Qty")
    c.drawString(4.8 * inch, y, "Unit Price")
    c.drawString(5.8 * inch, y, "Total")
    y -= 0.3 * inch

    c.setFont("Helvetica", 10)
    for desc, qty, unit_price, line_total in items:
        c.drawString(1 * inch, y, desc)
        c.drawString(4 * inch, y, str(qty))
        c.drawString(4.8 * inch, y, f"{currency} {unit_price:.2f}")
        c.drawString(5.8 * inch, y, f"{currency} {line_total:.2f}")
        y -= 0.25 * inch

    y -= 0.2 * inch
    c.line(4.5 * inch, y, 7 * inch, y)
    y -= 0.2 * inch

    c.setFont("Helvetica", 11)
    c.drawString(4.5 * inch, y, f"Subtotal:  {currency} {subtotal:.2f}")
    y -= 0.2 * inch
    c.drawString(4.5 * inch, y, f"Tax:       {currency} {tax:.2f}")
    y -= 0.2 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(4.5 * inch, y, f"Total:     {currency} {total:.2f}")


def make_invoice_clean(path):
    c = canvas.Canvas(path, pagesize=letter)
    items = [
        ("Consulting Services - Q2", 40, 150.00, 6000.00),
        ("Software License - Enterprise", 1, 2000.00, 2000.00),
        ("Cloud Hosting - 12 months", 12, 99.00, 1188.00),
        ("Onboarding & Training", 1, 2500.00, 2500.00),
    ]
    subtotal = float(sum(item[3] for item in items))
    tax = round(subtotal * 0.08, 2)
    total = subtotal + tax
    _draw_invoice(c, items, float(subtotal), float(tax), float(total))
    c.showPage()

    c.setFont("Helvetica-Bold", 14)
    c.drawString(1 * inch, 10 * inch, "Invoice - Page 2")
    c.setFont("Helvetica", 11)
    c.drawString(1 * inch, 9.5 * inch, "Terms: Net 30")
    c.drawString(1 * inch, 9.2 * inch, "Payment: Wire Transfer")
    c.drawString(1 * inch, 8.9 * inch, "Bank: Chase Business Account")
    c.drawString(1 * inch, 8.6 * inch, "Routing: 021000021")
    c.drawString(1 * inch, 8.3 * inch, "Account: 9876543210")
    c.drawString(1 * inch, 7.8 * inch, "Notes:")
    c.drawString(1 * inch, 7.5 * inch, "Thank you for your business!")
    c.showPage()
    c.save()
    print(f"  Created: {path}")


def make_invoice_broken(path):
    c = canvas.Canvas(path, pagesize=letter)
    items = [
        ("Consulting Services - Q2", 40, 150.00, 6000.00),
        ("Software License - Enterprise", 1, 2000.00, 2000.00),
        ("Cloud Hosting - 12 months", 12, 99.00, 1188.00),
        ("Premium Support", 1, 1500.00, 1500.00),
    ]
    # Items sum to 10688.00; subtotal is declared 5.00 too high so the
    # "sum(items) ≈ subtotal" check (FR-4) fails as designed for this sample.
    subtotal = 10693.00
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax, 2)
    _draw_invoice(
        c, items,
        subtotal=subtotal,
        tax=tax,
        total=total,
    )
    c.showPage()
    c.save()
    print(f"  Created: {path}")


def make_purchase_order(path):
    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(1 * inch, 10 * inch, "PURCHASE ORDER")

    c.setFont("Helvetica", 11)
    c.drawString(1 * inch, 9.5 * inch, "PO No: PO-2026-042")
    c.drawString(1 * inch, 9.2 * inch, "Date: July 5, 2026")
    c.drawString(1 * inch, 8.9 * inch, "Vendor: Office Supplies Inc.")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * inch, 8.3 * inch, "Ship To:")
    c.setFont("Helvetica", 11)
    c.drawString(1 * inch, 8.0 * inch, "Acme Corp - Warehouse B")
    c.drawString(1 * inch, 7.7 * inch, "456 Industrial Blvd")
    c.drawString(1 * inch, 7.4 * inch, "Chicago, IL 60601")

    y = 6.5 * inch
    c.setFont("Helvetica-Bold", 10)
    c.drawString(1 * inch, y, "Item")
    c.drawString(4 * inch, y, "Qty")
    c.drawString(4.8 * inch, y, "Unit Price")
    c.drawString(5.8 * inch, y, "Total")
    y -= 0.3 * inch

    c.setFont("Helvetica", 10)
    items = [
        ("Office Chairs (Ergonomic)", 10, 450.00, 4500.00),
        ("Standing Desks", 5, 800.00, 4000.00),
        ("Monitor Arms", 15, 75.00, 1125.00),
    ]
    for desc, qty, unit_price, line_total in items:
        c.drawString(1 * inch, y, desc)
        c.drawString(4 * inch, y, str(qty))
        c.drawString(4.8 * inch, y, f"USD {unit_price:.2f}")
        c.drawString(5.8 * inch, y, f"USD {line_total:.2f}")
        y -= 0.25 * inch

    y -= 0.2 * inch
    c.line(4.5 * inch, y, 7 * inch, y)
    y -= 0.2 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(4.5 * inch, y, "Total: USD 9,625.00")
    c.showPage()
    c.save()
    print(f"  Created: {path}")


def make_receipt_jpg(path):
    if Image is None:
        print("  Skipped receipt (Pillow not available)")
        return

    img = Image.new("RGB", (600, 800), "white")
    draw = ImageDraw.Draw(img)

    draw.text((40, 30), "QUICK MART GROCERY", fill="black")
    draw.text((40, 60), "123 Main Street", fill="black")
    draw.text((40, 80), "Anytown, USA", fill="black")
    draw.text((40, 110), "Date: 2026-07-08", fill="black")
    draw.text((40, 130), "Time: 14:32", fill="black")
    draw.line([(20, 150), (580, 150)], fill="black", width=2)

    items = [
        ("Milk 2% Gal", "1", "4.99"),
        ("Bread Wheat", "2", "5.98"),
        ("Eggs Dozen", "1", "6.49"),
        ("Bananas 2lb", "1", "3.50"),
        ("Coffee Beans", "1", "12.99"),
        ("Chicken Breast 1lb", "1", "8.99"),
    ]

    y = 170
    draw.text((40, y), "Item", fill="black")
    draw.text((350, y), "Qty", fill="black")
    draw.text((450, y), "Price", fill="black")
    y += 25

    for desc, qty, price in items:
        draw.text((40, y), desc, fill="black")
        draw.text((370, y), qty, fill="black")
        draw.text((450, y), f"${price}", fill="black")
        y += 22

    y += 10
    draw.line([(20, y), (580, y)], fill="black", width=1)
    y += 15
    draw.text((40, y), "SUBTOTAL", fill="black")
    draw.text((450, y), "$42.94", fill="black")
    y += 20
    draw.text((40, y), "TAX (8%)", fill="black")
    draw.text((450, y), "$3.44", fill="black")
    y += 20
    draw.text((40, y), "TOTAL", fill="black")
    draw.text((450, y), "$46.38", fill="black")
    y += 25
    draw.text((40, y), "Payment: Visa ****4242", fill="black")

    img.save(path, "JPEG", quality=80)
    print(f"  Created: {path}")


def main(output_dir):
    os.makedirs(output_dir, exist_ok=True)

    print("Generating samples...")
    make_invoice_clean(os.path.join(output_dir, "invoice_clean.pdf"))
    make_invoice_broken(os.path.join(output_dir, "invoice_broken_totals.pdf"))
    make_purchase_order(os.path.join(output_dir, "purchase_order.pdf"))
    make_receipt_jpg(os.path.join(output_dir, "receipt.jpg"))
    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    args = parser.parse_args()
    main(args.output_dir)
