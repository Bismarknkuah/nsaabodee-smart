class GiftDonation {
  final String id;
  final String funeralEventId;
  final String donorName;
  final String donorPhone;
  final String amountCash;
  final String giftItem;
  final String? estimatedItemValue;
  final String receiptNumber;
  final bool pendingSync;

  const GiftDonation({
    required this.id,
    required this.funeralEventId,
    required this.donorName,
    required this.donorPhone,
    required this.amountCash,
    required this.giftItem,
    required this.receiptNumber,
    this.estimatedItemValue,
    this.pendingSync = false,
  });

  double get totalValue => (double.tryParse(amountCash) ?? 0) + (double.tryParse(estimatedItemValue ?? '0') ?? 0);

  factory GiftDonation.fromApiJson(Map<String, dynamic> json) => GiftDonation(
        id: json['id'] as String,
        funeralEventId: json['funeral_event'] as String,
        donorName: json['donor_name'] as String,
        donorPhone: json['donor_phone'] as String? ?? '',
        amountCash: json['amount_cash'] as String,
        giftItem: json['gift_item'] as String? ?? '',
        estimatedItemValue: json['estimated_item_value'] as String?,
        receiptNumber: json['receipt_number'] as String,
        pendingSync: false,
      );

  factory GiftDonation.fromSqlite(Map<String, dynamic> row) => GiftDonation(
        id: row['id'] as String,
        funeralEventId: row['funeral_event_id'] as String,
        donorName: row['donor_name'] as String,
        donorPhone: row['donor_phone'] as String? ?? '',
        amountCash: row['amount_cash'] as String,
        giftItem: row['gift_item'] as String? ?? '',
        estimatedItemValue: row['estimated_item_value'] as String?,
        receiptNumber: row['receipt_number'] as String,
        pendingSync: (row['pending_sync'] as int? ?? 0) == 1,
      );

  Map<String, dynamic> toSqlite() => {
        'id': id,
        'funeral_event_id': funeralEventId,
        'donor_name': donorName,
        'donor_phone': donorPhone,
        'amount_cash': amountCash,
        'gift_item': giftItem,
        'estimated_item_value': estimatedItemValue,
        'receipt_number': receiptNumber,
        'pending_sync': pendingSync ? 1 : 0,
      };
}
