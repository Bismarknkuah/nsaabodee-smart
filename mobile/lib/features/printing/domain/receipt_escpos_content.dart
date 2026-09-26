import 'dart:typed_data';

import 'esc_pos_builder.dart';

/// Turns the same receipt data dict the backend's
/// `reports.receipts.contribution_receipt_data()` /
/// `gift_receipt_data()` produce (and which the app already fetches for
/// the on-screen ReceiptViewScreen) into ESC/POS bytes ready to send to
/// a thermal printer. Deliberately mirrors the layout of the backend's
/// own plain-text receipt (`reports/receipts.py`'s
/// `contribution_receipt_text` / `gift_receipt_text`) so the printed
/// slip and the electronic version always show the same information in
/// the same order.
class ReceiptEscPosContent {
  static Uint8List contribution(Map<String, dynamic> data, String communityName) {
    final b = EscPosBuilder()
      ..centerAlign()
      ..bold(true)
      ..line(communityName.toUpperCase())
      ..bold(false)
      ..line("Mandatory Contribution Receipt")
      ..leftAlign()
      ..divider()
      ..labelValue("Receipt:", data['receipt_number'] as String)
      ..labelValue("Date:", "${data['date']} ${data['time']}")
      ..labelValue("Member:", data['member_name'] as String)
      ..labelValue("No:", data['membership_number'] as String)
      ..labelValue("Family:", (data['family_name'] as String?) ?? "-")
      ..labelValue("Funeral:", data['funeral_deceased_name'] as String)
      ..labelValue("Paying:", data['rate_type'] == 'own_family' ? "Own family rate" : "General rate")
      ..divider()
      ..bold(true)
      ..doubleHeight(true)
      ..labelValue("AMOUNT", "GHS ${data['amount']}")
      ..doubleHeight(false)
      ..bold(false)
      ..labelValue("Method:", data['payment_method'] as String)
      ..labelValue("Balance:", "GHS ${data['obligation_balance_after']} (${data['obligation_status_after']})")
      ..divider()
      ..labelValue("Collector:", (data['collector_name'] as String?) ?? "-")
      ..newline()
      ..centerAlign()
      ..line("Thank you.")
      ..feedAndCut();
    return b.build();
  }

  static Uint8List gift(Map<String, dynamic> data, String communityName) {
    final b = EscPosBuilder()
      ..centerAlign()
      ..bold(true)
      ..line(communityName.toUpperCase())
      ..bold(false)
      ..line("Gift Donation Receipt")
      ..leftAlign()
      ..divider()
      ..labelValue("Receipt:", data['receipt_number'] as String)
      ..labelValue("Date:", "${data['date']} ${data['time']}")
      ..labelValue("Donor:", data['donor_name'] as String)
      ..labelValue("Family:", data['recipient_family_name'] as String)
      ..labelValue("Funeral:", data['funeral_deceased_name'] as String)
      ..divider();

    final amountCash = double.tryParse(data['amount_cash']?.toString() ?? '0') ?? 0;
    if (amountCash > 0) {
      b.labelValue("Cash:", "GHS ${data['amount_cash']}");
    }
    final giftItem = data['gift_item'] as String?;
    if (giftItem != null && giftItem.isNotEmpty) {
      b.labelValue("Item:", "$giftItem (~GHS ${data['estimated_item_value']})");
    }

    b
      ..bold(true)
      ..doubleHeight(true)
      ..labelValue("TOTAL", "GHS ${data['total_value']}")
      ..doubleHeight(false)
      ..bold(false)
      ..divider()
      ..labelValue("Collector:", (data['collector_name'] as String?) ?? "-")
      ..newline()
      ..centerAlign()
      ..line("With gratitude.")
      ..feedAndCut();
    return b.build();
  }
}
