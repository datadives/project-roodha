from __future__ import annotations

"""
/**
 * PROJECT ROODHA - v1.5.7 "Gold Baseline"
 * File: invoice_generator.py
 * 
 * 1) Purpose: Core framework configurations, middlewares, and utilities.
 * 2) Roadmap Connection: This file is a critical component of the Stage 2 (v1.5) Industrial 
 *    Hardening phase. It enforces multi-tenancy, security (RBAC), and transactional 
 *    resilience as defined in the formal Roadmap.
 */
"""
"""
invoice_generator.py
--------------------
V1.0 PDF Invoice Generator for Project Roodha.

Uses fpdf2 (FPDF2) to produce a clean A4 invoice with:
  - Project Roodha branding header
  - Tenant factory name and job metadata
  - Machine / Labour / Material cost breakdown table
  - 18% GST subtotal
  - Grand total

Encoding stability: Helvetica only (built-in, no external font files required).
Currency notation: "Rs." (ASCII-safe, avoids UTF-8 rupee symbol encoding issues in fpdf2).
"""

import io
from datetime import datetime
from decimal import Decimal


def _safe_float(value) -> float:
    """Convert Decimal / str / None to float safely."""
    if value is None:
        return 0.0
    try:
        return float(Decimal(str(value)))
    except Exception:
        return 0.0


def _fmt(value) -> str:
    """Format a number as 'Rs. X,XX,XXX.XX' for the invoice."""
    num = _safe_float(value)
    # Indian numbering: group first 3, then groups of 2
    parts = f"{num:,.2f}".split(".")
    integer_part = parts[0].replace(",", "")
    if len(integer_part) > 3:
        last3 = integer_part[-3:]
        rest = integer_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        integer_part = ",".join(groups) + "," + last3
    return f"Rs. {integer_part}.{parts[1]}"


def generate_invoice(job_data: dict) -> bytes:
    """
    Generate a PDF invoice from job_data and return it as bytes.

    Expected keys in job_data:
        job_id          str
        job_number      str
        customer_name   str  (optional)
        factory_name    str  – tenant's company_name
        due_date        str
        quantity        int
        quoted_price    float | None
        machine_cost    float | None
        labour_cost     float | None
        material_cost   float | None
        total_cost      float | None
        last_calculated_at  str | None
    """
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError(
            "fpdf2 is not installed. Run: pip install fpdf2"
        ) from exc

    # ── Colour palette (R, G, B) ────────────────────────────────────────────
    DARK = (15, 23, 42)      # slate-900
    MID = (100, 116, 139)    # slate-500
    LIGHT_BG = (248, 250, 252)  # slate-50
    EMERALD = (5, 150, 105)   # emerald-600
    WHITE = (255, 255, 255)
    BORDER = (226, 232, 240)  # slate-200

    GST_RATE = Decimal("0.18")

    machine_cost = Decimal(str(job_data.get("machine_cost") or 0))
    labour_cost = Decimal(str(job_data.get("labour_cost") or 0))
    material_cost = Decimal(str(job_data.get("material_cost") or 0))
    total_cost = Decimal(str(job_data.get("total_cost") or (machine_cost + labour_cost + material_cost)))
    gst_amount = (total_cost * GST_RATE).quantize(Decimal("0.01"))
    grand_total = (total_cost + gst_amount).quantize(Decimal("0.01"))
    quoted_price = Decimal(str(job_data.get("quoted_price") or 0))

    job_id = str(job_data.get("job_id", ""))
    job_number = str(job_data.get("job_number", job_id))
    factory_name = str(job_data.get("factory_name", "Factory"))
    customer_name = str(job_data.get("customer_name", "Customer"))
    due_date = str(job_data.get("due_date", ""))
    quantity = str(job_data.get("quantity", ""))
    generated_on = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)
    W = 174  # usable width (210 - 2×18)

    # ── HEADER BAND ─────────────────────────────────────────────────────────
    pdf.set_fill_color(*DARK)
    pdf.rect(0, 0, 210, 34, "F")

    pdf.set_xy(18, 9)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*WHITE)
    pdf.cell(W / 2, 8, "Project Roodha", ln=False)

    pdf.set_xy(18 + W / 2, 9)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(148, 163, 184)  # slate-400
    pdf.cell(W / 2, 8, "TAX INVOICE", align="R", ln=False)

    pdf.set_xy(18, 19)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(W, 6, factory_name, ln=True)

    # ── META ROW ────────────────────────────────────────────────────────────
    pdf.set_xy(18, 40)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*MID)

    meta_pairs = [
        ("Invoice No.", job_number),
        ("Job ID", job_id),
        ("Customer", customer_name),
        ("Quantity", str(quantity)),
        ("Due Date", str(due_date)),
        ("Generated", generated_on),
    ]
    col_w = W / 3
    for i, (label, val) in enumerate(meta_pairs):
        col = i % 3
        row = i // 3
        x = 18 + col * col_w
        y = 40 + row * 10
        pdf.set_xy(x, y)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*MID)
        pdf.cell(col_w * 0.45, 4, label.upper(), ln=False)
        pdf.set_xy(x + col_w * 0.45, y)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*DARK)
        pdf.cell(col_w * 0.55, 4, val, ln=False)

    # ── DIVIDER ─────────────────────────────────────────────────────────────
    pdf.set_draw_color(*BORDER)
    pdf.set_xy(18, 63)
    pdf.line(18, 63, 18 + W, 63)

    # ── COST BREAKDOWN TABLE ─────────────────────────────────────────────────
    table_y = 68
    col_desc = W * 0.55
    col_amt = W * 0.45

    # Table header
    pdf.set_fill_color(*DARK)
    pdf.set_xy(18, table_y)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*WHITE)
    pdf.cell(col_desc, 8, "  DESCRIPTION", fill=True, border=0, ln=False)
    pdf.cell(col_amt, 8, "AMOUNT", fill=True, border=0, align="R", ln=True)

    # Table rows
    rows = [
        ("Machine Cost", "Operation hours x machine hourly rate", machine_cost),
        ("Labour Cost", "Operation hours x worker hourly rate", labour_cost),
        ("Material Cost", f"Part cost/unit x {quantity} units", material_cost),
    ]

    row_colors = [LIGHT_BG, WHITE, LIGHT_BG]
    for idx, (title, desc, amount) in enumerate(rows):
        y_row = table_y + 8 + idx * 16
        pdf.set_fill_color(*row_colors[idx])
        pdf.set_xy(18, y_row)

        # Left cell — title + description stacked
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*DARK)
        pdf.cell(col_desc, 7, f"  {title}", fill=True, border=0, ln=False)
        pdf.set_xy(18 + col_amt, y_row)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*DARK)
        pdf.cell(col_amt, 7, _fmt(amount), fill=True, border=0, align="R", ln=True)

        pdf.set_fill_color(*row_colors[idx])
        pdf.set_xy(18, y_row + 7)
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*MID)
        pdf.cell(col_desc, 6, f"  {desc}", fill=True, border=0, ln=True)

    # ── SUBTOTAL / GST / TOTAL SECTION ──────────────────────────────────────
    sum_y = table_y + 8 + len(rows) * 16 + 6
    pdf.set_draw_color(*BORDER)
    pdf.line(18, sum_y, 18 + W, sum_y)

    subtotal_rows = [
        ("Subtotal (Cost of Production)", total_cost, False),
        (f"GST @ 18%  (placeholder — verify with CA)", gst_amount, False),
        ("Grand Total (incl. GST)", grand_total, True),
    ]
    if quoted_price > 0:
        margin = quoted_price - grand_total
        subtotal_rows.append(
            (f"Quoted Price  /  Gross Margin", f"{_fmt(quoted_price)}  ({_fmt(margin)})", False)
        )

    for label, value, bold in subtotal_rows:
        y_sub = sum_y + 4
        pdf.set_xy(18, y_sub)

        if bold:
            pdf.set_fill_color(*EMERALD)
            pdf.rect(18, y_sub - 1, W, 10, "F")
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*WHITE)
        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(*MID)

        pdf.cell(col_desc, 8, f"  {label}", border=0, ln=False)
        if bold:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*WHITE)
        else:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*DARK)

        val_str = _fmt(value) if isinstance(value, Decimal) else str(value)
        pdf.cell(col_amt, 8, val_str, border=0, align="R", ln=True)
        sum_y += 10 if not bold else 11

    # ── FOOTER ──────────────────────────────────────────────────────────────
    footer_y = 272
    pdf.set_draw_color(*BORDER)
    pdf.line(18, footer_y, 18 + W, footer_y)
    pdf.set_xy(18, footer_y + 3)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MID)
    pdf.cell(
        W,
        5,
        "This is a system-generated document from Project Roodha. "
        "GST figures are indicative — please consult your CA before filing.",
        align="C",
    )

    # ── OUTPUT ──────────────────────────────────────────────────────────────
    buffer = io.BytesIO()
    pdf_bytes = pdf.output()
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin-1")
    buffer.write(pdf_bytes)
    buffer.seek(0)
    return buffer.read()
