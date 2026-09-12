class FuneralExpense {
  final String id;
  final String funeralEventId;
  final String description;
  final String category;
  final String amount;
  final String paymentMethod;
  final String voucherNumber;
  final String incurredOn;
  final bool pendingSync;

  const FuneralExpense({
    required this.id,
    required this.funeralEventId,
    required this.description,
    required this.category,
    required this.amount,
    required this.paymentMethod,
    required this.voucherNumber,
    required this.incurredOn,
    this.pendingSync = false,
  });

  factory FuneralExpense.fromApiJson(Map<String, dynamic> json) => FuneralExpense(
        id: json['id'] as String,
        funeralEventId: json['funeral_event'] as String,
        description: json['description'] as String,
        category: json['category'] as String,
        amount: json['amount'] as String,
        paymentMethod: json['payment_method'] as String,
        voucherNumber: json['voucher_number'] as String,
        incurredOn: json['incurred_on'] as String,
        pendingSync: false,
      );

  factory FuneralExpense.fromSqlite(Map<String, dynamic> row) => FuneralExpense(
        id: row['id'] as String,
        funeralEventId: row['funeral_event_id'] as String,
        description: row['description'] as String,
        category: row['category'] as String,
        amount: row['amount'] as String,
        paymentMethod: row['payment_method'] as String,
        voucherNumber: row['voucher_number'] as String,
        incurredOn: row['incurred_on'] as String,
        pendingSync: (row['pending_sync'] as int? ?? 0) == 1,
      );

  Map<String, dynamic> toSqlite() => {
        'id': id,
        'funeral_event_id': funeralEventId,
        'description': description,
        'category': category,
        'amount': amount,
        'payment_method': paymentMethod,
        'voucher_number': voucherNumber,
        'incurred_on': incurredOn,
        'pending_sync': pendingSync ? 1 : 0,
      };
}

class FuneralAttendanceRecord {
  final String id;
  final String funeralEventId;
  final String? memberId;
  final String displayName;
  final bool pendingSync;

  const FuneralAttendanceRecord({
    required this.id,
    required this.funeralEventId,
    required this.displayName,
    this.memberId,
    this.pendingSync = false,
  });

  factory FuneralAttendanceRecord.fromApiJson(Map<String, dynamic> json) => FuneralAttendanceRecord(
        id: json['id'] as String,
        funeralEventId: json['funeral_event'] as String,
        memberId: json['member'] as String?,
        displayName: json['display_name'] as String,
        pendingSync: false,
      );

  factory FuneralAttendanceRecord.fromSqlite(Map<String, dynamic> row) => FuneralAttendanceRecord(
        id: row['id'] as String,
        funeralEventId: row['funeral_event_id'] as String,
        memberId: row['member_id'] as String?,
        displayName: row['display_name'] as String,
        pendingSync: (row['pending_sync'] as int? ?? 0) == 1,
      );

  Map<String, dynamic> toSqlite() => {
        'id': id,
        'funeral_event_id': funeralEventId,
        'member_id': memberId,
        'display_name': displayName,
        'pending_sync': pendingSync ? 1 : 0,
      };
}
