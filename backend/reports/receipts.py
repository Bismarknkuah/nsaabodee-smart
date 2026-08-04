"""
Printable receipts for both ledgers. A receipt is read-only, derived
entirely from data that already exists (ContributionPayment or
GiftDonation) — nothing here writes anything. Two output shapes are
produced for the same receipt:

  - a structured dict (for on-screen display / a PDF-style printout)
  - a plain monospaced text block sized for a Bluetooth thermal printer
    (the master brief's "Bluetooth thermal printer support" — this is
    the actual bytes/text such a printer would be handed; wiring a real
    Bluetooth ESC/POS SDK is a device-integration task for the mobile
    app, out of scope for this backend module, but the exact text it
    would print is generated here so that integration has something
    concrete to send).
"""

from funerals.models import ContributionPayment
from gifts.models import GiftDonation


def contribution_receipt_data(payment: ContributionPayment) -> dict:
    obligation = payment.obligation
    member = obligation.member
    funeral = obligation.funeral_event
    return {
        "ledger": "contribution",
        "receipt_number": payment.receipt_number,
        "member_name": member.full_name,
        "membership_number": member.membership_number,
        "family_name": member.family.name if member.family else None,
        "rate_type": obligation.rate_type,
        "amount": str(payment.amount),
        "payment_method": payment.method,
        # Cash is handed over in person, so the natural moment to give a
        # receipt is a physical printout there and then. Every other
        # method (mobile money, bank, other) is already a digital
        # transaction on the payer's end, so there's no in-person moment
        # to hand over paper — the receipt is electronic by default. This
        # is a UX default, not a restriction: a cash receipt is ALSO
        # always available electronically in the payer's dashboard (see
        # reports.services.my_receipts), and any receipt can still be
        # printed manually regardless of this classification.
        "delivery_channel": "physical" if payment.method == "cash" else "electronic",
        "printed_at": payment.printed_at.isoformat() if payment.printed_at else None,
        "funeral_deceased_name": funeral.deceased_name,
        "deceased_date_of_birth": _isoformat(funeral.deceased_date_of_birth) if funeral.deceased_date_of_birth else None,
        "collector_name": payment.collected_by.get_full_name() if payment.collected_by else None,
        "date": payment.paid_at.date().isoformat(),
        "time": payment.paid_at.time().strftime("%H:%M"),
        "obligation_balance_after": str(obligation.balance),
        "obligation_status_after": obligation.payment_status,
    }


def _isoformat(value) -> str:
    """
    `date_of_death` is a real `datetime.date` when a FuneralEvent is
    created through the API (DRF's DateField parses the incoming JSON
    string), but stays a plain Python `str` when a service function is
    called directly with a string literal and never passes through that
    validation — a real, valid code path (funerals.services.create_funeral_event
    accepts either), not a data-corruption case. Handles both rather
    than assuming the API is the only caller.
    """
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def gift_receipt_data(donation: GiftDonation) -> dict:
    # An item-only gift (no cash) has no "payment method" in the usual
    # sense — it's never handed over as a physical banknote receipt
    # moment, so it defaults to electronic same as any non-cash method.
    delivery_channel = "physical" if donation.payment_method == "cash" else "electronic"
    receiver_name = donation.received_by_member.full_name if donation.received_by_member else None
    appreciation_target = receiver_name or donation.recipient_family.name
    return {
        "ledger": "gift",
        "receipt_number": donation.receipt_number,
        "donor_name": donation.donor_name,
        "donor_phone": donation.donor_phone,
        "donor_hometown": donation.donor_hometown,
        "recipient_family_name": donation.recipient_family.name,
        "received_by_member_name": receiver_name,
        "relationship_to_recipient": donation.relationship_to_recipient,
        "connected_relative_name": donation.connected_relative_name,
        "amount_cash": str(donation.amount_cash),
        "gift_item": donation.gift_item,
        "estimated_item_value": str(donation.estimated_item_value) if donation.estimated_item_value else None,
        "total_value": str(donation.total_value),
        "payment_method": donation.payment_method,
        "delivery_channel": delivery_channel,
        "printed_at": donation.printed_at.isoformat() if donation.printed_at else None,
        "funeral_deceased_name": donation.funeral_event.deceased_name,
        "deceased_date_of_birth": _isoformat(donation.funeral_event.deceased_date_of_birth) if donation.funeral_event.deceased_date_of_birth else None,
        "collector_name": donation.collected_by.get_full_name() if donation.collected_by else None,
        "date": donation.given_at.date().isoformat(),
        "time": donation.given_at.time().strftime("%H:%M"),
        "appreciation_message": (
            f"Thank you, {donation.donor_name}, for your kindness to {appreciation_target} "
            f"in loving memory of {donation.funeral_event.deceased_name}."
        ),
    }


def _thermal_line(width: int = 32) -> str:
    return "-" * width


def contribution_receipt_text(payment: ContributionPayment, community_name: str) -> str:
    data = contribution_receipt_data(payment)
    lines = [
        community_name.upper().center(32),
        "MANDATORY CONTRIBUTION RECEIPT".center(32),
        _thermal_line(),
        f"Receipt:  {data['receipt_number']}",
        f"Date:     {data['date']} {data['time']}",
        f"Member:   {data['member_name']}",
        f"No:       {data['membership_number']}",
        f"Family:   {data['family_name'] or '-'}",
        f"Funeral:  {data['funeral_deceased_name']}",
    ]
    if data.get("deceased_date_of_birth"):
        lines.append(f"Born:     {data['deceased_date_of_birth']}")
    lines += [
        f"Paying:   {'Own family rate' if data['rate_type'] == 'own_family' else 'General rate'}",
        _thermal_line(),
        f"AMOUNT:   GHS {data['amount']}",
        f"Method:   {data['payment_method']}",
        f"Balance:  GHS {data['obligation_balance_after']} ({data['obligation_status_after']})",
        _thermal_line(),
        f"Collector: {data['collector_name'] or '-'}",
        "",
        "Thank you.".center(32),
    ]
    return "\n".join(lines)


def gift_receipt_text(donation: GiftDonation, community_name: str) -> str:
    data = gift_receipt_data(donation)
    gift_line = None
    if data["gift_item"]:
        gift_line = f"Item:     {data['gift_item']} (~GHS {data['estimated_item_value']})"
    lines = [
        community_name.upper().center(32),
        "GIFT DONATION RECEIPT".center(32),
        _thermal_line(),
        f"Receipt:  {data['receipt_number']}",
        f"Date:     {data['date']} {data['time']}",
        f"Donor:    {data['donor_name']}",
    ]
    if data["donor_hometown"]:
        lines.append(f"From:     {data['donor_hometown']}")
    lines += [
        f"Deceased: {data['funeral_deceased_name']}",
        f"Date of birth: {data['deceased_date_of_birth'] or 'not recorded'}",
    ]
    if data["received_by_member_name"]:
        lines.append(f"Given to: {data['received_by_member_name']}")
        if data["relationship_to_recipient"]:
            lines.append(f"Relation: {data['relationship_to_recipient']}")
    else:
        lines.append(f"Family:   {data['recipient_family_name']}")
    lines.append(_thermal_line())
    if float(data["amount_cash"]) > 0:
        lines.append(f"Cash:     GHS {data['amount_cash']}")
    if gift_line:
        lines.append(gift_line)
    lines += [
        f"TOTAL VALUE: GHS {data['total_value']}",
        _thermal_line(),
        f"Collector: {data['collector_name'] or '-'}",
        "",
        data["appreciation_message"],
    ]
    return "\n".join(lines)


def fund_contribution_receipt_data(contribution) -> dict:
    """
    "The system should print individual receipts once money is entered
    paid" — applies to Family Fund contributions exactly the same way it
    already does to mandatory contributions and gifts, since a family's
    own private fund still deserves a real receipt trail, just one that
    never touches the community-wide ledgers.
    """
    return {
        "ledger": "family_fund",
        "receipt_number": contribution.receipt_number,
        "fund_name": contribution.fund.name,
        "family_name": contribution.fund.family.name,
        "member_name": contribution.member.full_name,
        "amount": str(contribution.amount),
        "payment_method": contribution.payment_method,
        "date": contribution.paid_at.date().isoformat(),
        "time": contribution.paid_at.time().strftime("%H:%M"),
        "recorded_by_name": contribution.recorded_by.get_full_name() if contribution.recorded_by else None,
    }


def fund_contribution_receipt_text(contribution, community_name: str) -> str:
    data = fund_contribution_receipt_data(contribution)
    lines = [
        community_name.upper().center(32),
        f"{data['family_name']} FAMILY FUND".center(32),
        _thermal_line(),
        f"Receipt:  {data['receipt_number']}",
        f"Date:     {data['date']} {data['time']}",
        f"Fund:     {data['fund_name']}",
        f"Member:   {data['member_name']}",
        _thermal_line(),
        f"AMOUNT: GHS {data['amount']}",
        f"Method:   {data['payment_method']}",
        _thermal_line(),
        f"Recorded by: {data['recorded_by_name'] or '-'}",
        "",
        "Private family fund — not part of".center(32),
        "the community ledger.".center(32),
    ]
    return "\n".join(lines)


def funeral_expense_voucher_data(expense) -> dict:
    """
    A paper trail for an APPROVED family funeral expense — the seller,
    the family, and whoever paid all have something concrete showing
    this purchase was properly authorized, not just recorded.
    """
    return {
        "ledger": "family_funeral_expense",
        "family_name": expense.family.name,
        "funeral_deceased_name": expense.funeral_event.deceased_name,
        "item_name": expense.item_name,
        "seller_name": expense.seller_name,
        "seller_contact": expense.seller_contact,
        "amount": str(expense.amount),
        "date_purchased": expense.date_purchased.isoformat() if hasattr(expense.date_purchased, "isoformat") else str(expense.date_purchased),
        "paid_by_member_name": expense.paid_by_member.full_name if expense.paid_by_member else None,
        "status": expense.status,
        "approved_by_name": expense.approved_by.get_full_name() if expense.approved_by else None,
        "approved_at": expense.approved_at.isoformat() if expense.approved_at else None,
    }


def funeral_expense_voucher_text(expense, community_name: str) -> str:
    data = funeral_expense_voucher_data(expense)
    if data["status"] != "approved":
        return f"No voucher available — this expense is currently '{data['status']}', not approved."
    lines = [
        community_name.upper().center(32),
        f"{data['family_name']} EXPENSE VOUCHER".center(32),
        _thermal_line(),
        f"Item:     {data['item_name']}",
        f"Seller:   {data['seller_name']}",
    ]
    if data["seller_contact"]:
        lines.append(f"Contact:  {data['seller_contact']}")
    lines += [
        f"Date:     {data['date_purchased']}",
        f"Funeral:  {data['funeral_deceased_name']}",
    ]
    if data["paid_by_member_name"]:
        lines.append(f"Paid by:  {data['paid_by_member_name']}")
    lines += [
        _thermal_line(),
        f"AMOUNT: GHS {data['amount']}",
        _thermal_line(),
        f"Approved by: {data['approved_by_name'] or '-'}",
        "",
        "APPROVED — private family expense,".center(32),
        "not part of the community ledger.".center(32),
    ]
    return "\n".join(lines)
