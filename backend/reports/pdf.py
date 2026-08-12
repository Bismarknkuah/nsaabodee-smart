"""
PDF generation for receipts and statements — a presentation layer on top
of the exact same data already produced by receipts.py and services.py.
Nothing in this file computes anything new; it only lays out numbers
that were already correct before this file existed.

Uses ReportLab (pure Python, no system-level dependencies like Cairo/
Pango), so it works the same in any environment without extra install
steps beyond `pip install reportlab`.
"""

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A6
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("ReceiptTitle", parent=_STYLES["Heading2"], alignment=1, spaceAfter=2)
_SUBTITLE_STYLE = ParagraphStyle("ReceiptSubtitle", parent=_STYLES["Normal"], alignment=1, textColor=colors.grey)
_LABEL_STYLE = ParagraphStyle("Label", parent=_STYLES["Normal"], textColor=colors.grey, fontSize=9)


def _money(value) -> str:
    return f"GH\u20b5 {Decimal(str(value)):.2f}"


def contribution_receipt_pdf(data: dict, community_name: str) -> bytes:
    """
    A small receipt-slip PDF (A6, roughly the size of a till receipt) for
    one ContributionPayment. `data` is exactly what
    reports.receipts.contribution_receipt_data() returns.
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A6)
    width, height = A6

    y = height - 15 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y, community_name.upper())
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, "Mandatory Contribution Receipt")
    y -= 8 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 6 * mm

    rows = [
        ("Receipt No.", data["receipt_number"]),
        ("Date / Time", f"{data['date']}  {data['time']}"),
        ("Member", data["member_name"]),
        ("Membership No.", data["membership_number"]),
        ("Family", data["family_name"] or "-"),
        ("Funeral", data["funeral_deceased_name"]),
    ]
    if data.get("deceased_date_of_birth"):
        rows.append(("Date of birth", data["deceased_date_of_birth"]))
    rows.append(("Paying As", "Own family rate" if data["rate_type"] == "own_family" else "General rate"))
    c.setFont("Helvetica", 8)
    for label, value in rows:
        c.setFillColor(colors.grey)
        c.drawString(8 * mm, y, label)
        c.setFillColor(colors.black)
        c.drawRightString(width - 8 * mm, y, str(value))
        y -= 5 * mm

    y -= 2 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(8 * mm, y, "AMOUNT")
    c.drawRightString(width - 8 * mm, y, _money(data["amount"]))
    y -= 7 * mm
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawString(8 * mm, y, f"Method: {data['payment_method']}")
    y -= 5 * mm
    c.drawString(8 * mm, y, f"Balance after: {_money(data['obligation_balance_after'])} ({data['obligation_status_after']})")
    y -= 8 * mm
    c.setFillColor(colors.black)
    c.drawString(8 * mm, y, f"Collector: {data['collector_name'] or '-'}")
    y -= 10 * mm
    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, y, "Thank you.")

    c.showPage()
    c.save()
    return buffer.getvalue()


def gift_receipt_pdf(data: dict, community_name: str) -> bytes:
    """Same slip format as contribution_receipt_pdf, for one GiftDonation."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A6)
    width, height = A6

    y = height - 15 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y, community_name.upper())
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, "Gift Donation Receipt")
    y -= 8 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 6 * mm

    rows = [
        ("Receipt No.", data["receipt_number"]),
        ("Date / Time", f"{data['date']}  {data['time']}"),
        ("Donor", data["donor_name"]),
    ]
    if data.get("donor_hometown"):
        rows.append(("From", data["donor_hometown"]))
    rows += [
        ("Deceased", data["funeral_deceased_name"]),
    ]
    if data.get("deceased_date_of_birth"):
        rows.append(("Date of birth", data["deceased_date_of_birth"]))
    if data.get("received_by_member_name"):
        rows.append(("Given to", data["received_by_member_name"]))
        if data.get("relationship_to_recipient"):
            rows.append(("Relationship", data["relationship_to_recipient"]))
    else:
        rows.append(("Family", data["recipient_family_name"]))

    c.setFont("Helvetica", 8)
    for label, value in rows:
        c.setFillColor(colors.grey)
        c.drawString(8 * mm, y, label)
        c.setFillColor(colors.black)
        c.drawRightString(width - 8 * mm, y, str(value))
        y -= 5 * mm

    if float(data["amount_cash"]) > 0:
        c.setFillColor(colors.grey)
        c.drawString(8 * mm, y, "Cash")
        c.setFillColor(colors.black)
        c.drawRightString(width - 8 * mm, y, _money(data["amount_cash"]))
        y -= 5 * mm
    if data["gift_item"]:
        c.setFillColor(colors.grey)
        c.drawString(8 * mm, y, "Item")
        c.setFillColor(colors.black)
        c.drawRightString(width - 8 * mm, y, f"{data['gift_item']} (~{_money(data['estimated_item_value'])})")
        y -= 5 * mm

    y -= 2 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(8 * mm, y, "TOTAL VALUE")
    c.drawRightString(width - 8 * mm, y, _money(data["total_value"]))
    y -= 9 * mm
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    c.drawString(8 * mm, y, f"Collector: {data['collector_name'] or '-'}")
    y -= 10 * mm
    c.setFont("Helvetica-Oblique", 8)
    # The appreciation message is a full sentence, not a short centred
    # label — wrapped by hand across the 32mm-ish usable width rather
    # than assuming it fits one line the way "With gratitude." always did.
    import textwrap
    for line in textwrap.wrap(data["appreciation_message"], width=40):
        c.drawCentredString(width / 2, y, line)
        y -= 4 * mm

    c.showPage()
    c.save()
    return buffer.getvalue()


def _statement_doc(community_name: str, title: str, subtitle: str = "") -> tuple:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm)
    elements = [
        Paragraph(community_name.upper(), _TITLE_STYLE),
        Paragraph(title, _SUBTITLE_STYLE),
    ]
    if subtitle:
        elements.append(Paragraph(subtitle, _SUBTITLE_STYLE))
    elements.append(Spacer(1, 8 * mm))
    return buffer, doc, elements


def _styled_table(data) -> Table:
    table = Table(data, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6E4E")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DED6C4")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F0E6")]),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def collections_report_pdf(report: dict, community_name: str, period_label: str) -> bytes:
    """PDF version of a daily/weekly/monthly/annual collections statement."""
    buffer, doc, elements = _statement_doc(
        community_name, f"Collections Statement — {period_label}",
        f"{report['start_date']} to {report['end_date']}",
    )

    elements.append(Paragraph("Mandatory Contributions", _STYLES["Heading3"]))
    elements.append(_styled_table([
        ["Method", "Amount"],
        *[[m.replace("_", " ").title(), _money(v)] for m, v in report["contributions"]["by_method"].items()],
        ["Total", _money(report["contributions"]["total"])],
    ]))
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("Gift Donations (cash portion)", _STYLES["Heading3"]))
    elements.append(_styled_table([
        ["Method", "Amount"],
        *[[m.replace("_", " ").title(), _money(v)] for m, v in report["gift_cash"]["by_method"].items()],
        ["Total", _money(report["gift_cash"]["total"])],
    ]))
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("Combined Cash In Hand", _STYLES["Heading3"]))
    elements.append(_styled_table([
        ["Method", "Amount"],
        *[[m.replace("_", " ").title(), _money(v)] for m, v in report["combined_cash_position_by_method"].items()],
    ]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(f"Receipts issued: {report['receipts_issued']}", _LABEL_STYLE))

    doc.build(elements)
    return buffer.getvalue()


def family_statement_pdf(statement: dict, community_name: str) -> bytes:
    """
    The abusuapanin's (family head's) printable statement: all four
    ledgers a funeral of his family actually touches — Family, Community,
    Guest, and Town Leaders — plus what his own members paid as
    outsiders on other families' funerals, for historical context.

    Guest/Town Leaders/donation-receiver sections only render if present
    in `statement` — a committee member (not this family's own head)
    hitting this same PDF endpoint gets those keys stripped upstream
    (see reports/views.py's FamilyStatementView), so the PDF they
    receive is honestly just the Family/Community ledgers, not a PDF
    with blank/zeroed donation figures pretending there's nothing to see.
    """
    buffer, doc, elements = _statement_doc(community_name, f"Family Statement — {statement['family_name']}")

    elements.append(Paragraph("The Two Mandatory Ledgers", _STYLES["Heading3"]))
    elements.append(_styled_table([
        ["Ledger", "Expected", "Collected"],
        ["Family Ledger (own members, own-family rate)",
         _money(statement["family_ledger"]["expected_total"]), _money(statement["family_ledger"]["collected_total"])],
        ["Community Ledger (general rate, from everyone else)",
         _money(statement["community_ledger"]["expected_total"]), _money(statement["community_ledger"]["collected_total"])],
    ]))

    if "guest_ledger" in statement and "town_leaders_ledger" in statement:
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph("The Donation Ledgers", _STYLES["Heading3"]))
        elements.append(_styled_table([
            ["Ledger", "Donor count", "Total value"],
            ["Guest Ledger (visiting well-wishers)",
             str(statement["guest_ledger"]["donor_count"]), _money(statement["guest_ledger"]["total_value"])],
            ["Town Leaders Ledger (King & Elders)",
             str(statement["town_leaders_ledger"]["donor_count"]), _money(statement["town_leaders_ledger"]["total_value"])],
        ]))

    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("For Context", _STYLES["Heading3"]))
    elements.append(_styled_table([
        ["", "Expected", "Collected"],
        ["Members as outsiders on other families' funerals",
         _money(statement["members_as_outsiders_elsewhere"]["expected_total"]),
         _money(statement["members_as_outsiders_elsewhere"]["collected_total"])],
    ]))

    if statement.get("donation_receivers"):
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph("Donation Accountability — Who Received What", _STYLES["Heading3"]))
        elements.append(_styled_table([
            ["Receiver", "Donations", "Total received"],
            *[[r["member_name"], str(r["donation_count"]), _money(r["total_received"])]
              for r in statement["donation_receivers"]],
        ]))

    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(f"Active members: {statement['member_count']}", _LABEL_STYLE))

    doc.build(elements)
    return buffer.getvalue()


def family_expenses_pdf(*, community_name: str, family_name: str, summary: dict, expenses: list, deceased_name: str = None) -> bytes:
    """
    'Family expenses should also be printable or downloaded.' A real,
    itemized statement — not just the summary totals, since the
    abusuapanin reviewing this needs to see exactly what each recorded
    purchase was, not only the buckets it falls into.
    """
    title = f"Family Expenses — {family_name}"
    subtitle = f"For {deceased_name}'s funeral" if deceased_name else "All funerals"
    buffer, doc, elements = _statement_doc(community_name, title, subtitle)

    elements.append(Paragraph("Summary by Status", _STYLES["Heading3"]))
    elements.append(_styled_table([
        ["Status", "Count", "Total"],
        ["Pending Approval", str(summary["pending"]["count"]), _money(summary["pending"]["total"])],
        ["Approved", str(summary["approved"]["count"]), _money(summary["approved"]["total"])],
        ["Rejected", str(summary["rejected"]["count"]), _money(summary["rejected"]["total"])],
        ["All Recorded", "", _money(summary["total_all_recorded"])],
    ]))
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("Itemized Expenses", _STYLES["Heading3"]))
    if expenses:
        elements.append(_styled_table([
            ["Item", "Seller", "Bought By", "Status", "Date", "Amount"],
            *[[
                e["item_name"] or "—", e["seller_name"] or "—", e.get("paid_by_member_name") or "—",
                e["status"].replace("_", " ").title(), e["date_purchased"], _money(e["amount"]),
            ] for e in expenses],
        ]))
    else:
        elements.append(Paragraph("No expenses recorded yet.", _LABEL_STYLE))

    doc.build(elements)
    return buffer.getvalue()


def _donor_entries_table(entries: list) -> Table:
    """
    "When printing or generating list of those who paid: the name, phone
    contact, where the gifter resides, the amount the gifter paid" —
    this table is that list, verbatim, for however many donor entries
    `gifts.services.donations_received_by_member`'s `entries` list has.
    """
    rows = [["Donor", "Phone", "Hometown", "Amount"]]
    for e in entries:
        rows.append([e["donor_name"], e.get("donor_phone") or "-", e.get("donor_hometown") or "-", _money(e["amount"])])
    return _styled_table(rows)


def donation_receiver_statement_pdf(*, community_name: str, member_name: str, entries: list, deceased_name: str | None = None) -> bytes:
    """
    One receiver's printable donor list — "after the funeral all should
    be able to print receipts to all those who received donations, but
    those who donated to Adwoa only should be shown to Adwoa." This is
    Adwoa's own copy: every donor who gave to her by name, with exactly
    the columns asked for.
    """
    title = f"Donations Received — {member_name}"
    subtitle = f"For {deceased_name}'s funeral" if deceased_name else "Across all funerals"
    buffer, doc, elements = _statement_doc(community_name, title, subtitle)

    total = sum((float(e["amount"]) for e in entries), 0.0)
    elements.append(Paragraph(f"Total received: GH₵ {total:,.2f} ({len(entries)} donation(s))", _LABEL_STYLE))
    elements.append(Spacer(1, 4 * mm))
    elements.append(_donor_entries_table(entries))

    doc.build(elements)
    return buffer.getvalue()


def all_receivers_donation_statement_pdf(*, community_name: str, deceased_name: str, receivers: list) -> bytes:
    """
    The family head/admin version — every registered receiver for this
    funeral, each with their own donor list kept visibly separate
    section-by-section (never merged into one undifferentiated pool),
    matching "those who donated to Adwoa only should be shown to Adwoa
    and same Yaw's own should be list of donations paid to Yaw" — this
    document just puts both of those separate lists behind one cover
    page for whoever has legitimate oversight of the whole funeral.
    """
    buffer, doc, elements = _statement_doc(community_name, f"All Donation Receivers — {deceased_name}'s Funeral")

    for receiver in receivers:
        elements.append(Paragraph(
            f"{receiver['member_name']} — GH₵ {float(receiver['total_received']):,.2f} ({receiver['donation_count']} donation(s))",
            _STYLES["Heading3"],
        ))
        if receiver["entries"]:
            elements.append(_donor_entries_table(receiver["entries"]))
        else:
            elements.append(Paragraph("No donations recorded yet.", _LABEL_STYLE))
        elements.append(Spacer(1, 6 * mm))

    doc.build(elements)
    return buffer.getvalue()


def fund_contribution_receipt_pdf(data: dict, community_name: str) -> bytes:
    """Same A6 slip format as every other receipt in this platform, for one FamilyFundContribution."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A6)
    width, height = A6

    y = height - 15 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y, community_name.upper())
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, f"{data['family_name']} Family Fund Receipt")
    y -= 8 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 6 * mm

    rows = [
        ("Receipt No.", data["receipt_number"]),
        ("Date / Time", f"{data['date']}  {data['time']}"),
        ("Fund", data["fund_name"]),
        ("Member", data["member_name"]),
        ("Method", data["payment_method"]),
    ]
    c.setFont("Helvetica", 8)
    for label, value in rows:
        c.setFillColor(colors.grey)
        c.drawString(8 * mm, y, label)
        c.setFillColor(colors.black)
        c.drawRightString(width - 8 * mm, y, str(value))
        y -= 5 * mm

    y -= 2 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(8 * mm, y, "AMOUNT")
    c.drawRightString(width - 8 * mm, y, _money(data["amount"]))
    y -= 9 * mm
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    c.drawString(8 * mm, y, f"Recorded by: {data['recorded_by_name'] or '-'}")
    y -= 10 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width / 2, y, "Private family fund — not part of the community ledger.")

    c.showPage()
    c.save()
    return buffer.getvalue()


def funeral_expense_voucher_pdf(data: dict, community_name: str) -> bytes:
    """An A6 voucher for one APPROVED FamilyFuneralExpense — the seller/family's proof this purchase was authorized."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A6)
    width, height = A6

    y = height - 15 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y, community_name.upper())
    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, f"{data['family_name']} Expense Voucher")
    y -= 8 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 6 * mm

    rows = [
        ("Item", data["item_name"]),
        ("Seller", data["seller_name"]),
        ("Date", data["date_purchased"]),
        ("Funeral", data["funeral_deceased_name"]),
    ]
    if data.get("seller_contact"):
        rows.insert(2, ("Contact", data["seller_contact"]))
    if data.get("paid_by_member_name"):
        rows.append(("Paid by", data["paid_by_member_name"]))

    c.setFont("Helvetica", 8)
    for label, value in rows:
        c.setFillColor(colors.grey)
        c.drawString(8 * mm, y, label)
        c.setFillColor(colors.black)
        c.drawRightString(width - 8 * mm, y, str(value))
        y -= 5 * mm

    y -= 2 * mm
    c.line(8 * mm, y, width - 8 * mm, y)
    y -= 7 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(8 * mm, y, "AMOUNT")
    c.drawRightString(width - 8 * mm, y, _money(data["amount"]))
    y -= 9 * mm
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.black)
    c.drawString(8 * mm, y, f"Approved by: {data['approved_by_name'] or '-'}")
    y -= 10 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width / 2, y, "APPROVED — private family expense, not part of the community ledger.")

    c.showPage()
    c.save()
    return buffer.getvalue()
