enum FuneralStatus { active, closed, cancelled }

FuneralStatus funeralStatusFromString(String value) => FuneralStatus.values.byName(value);

class FuneralEvent {
  final String id;
  final String deceasedName;
  final String deceasedGender;
  final String deceasedFamilyId;
  final String deceasedFamilyName;
  final DateTime dateOfDeath;
  final DateTime collectionStartDate;
  final FuneralStatus status;
  final String ownFamilyAmount;
  final String generalMaleAmount;
  final String generalFemaleAmount;

  /// True while this funeral was created offline and hasn't been
  /// confirmed by the server yet. Its ledger (ContributionObligation
  /// fan-out) is generated server-side, so a still-pending funeral has no
  /// obligations to show locally until sync completes — the UI should
  /// make that wait visible rather than pretend the ledger already exists.
  final bool pendingSync;

  const FuneralEvent({
    required this.id,
    required this.deceasedName,
    required this.deceasedGender,
    required this.deceasedFamilyId,
    required this.deceasedFamilyName,
    required this.dateOfDeath,
    required this.collectionStartDate,
    required this.status,
    required this.ownFamilyAmount,
    required this.generalMaleAmount,
    required this.generalFemaleAmount,
    this.pendingSync = false,
  });

  factory FuneralEvent.fromApiJson(Map<String, dynamic> json) => FuneralEvent(
        id: json['id'] as String,
        deceasedName: json['deceased_name'] as String,
        deceasedGender: json['deceased_gender'] as String,
        deceasedFamilyId: json['deceased_family'] as String,
        deceasedFamilyName: json['deceased_family_name'] as String,
        dateOfDeath: DateTime.parse(json['date_of_death'] as String),
        collectionStartDate: DateTime.parse(json['collection_start_date'] as String),
        status: funeralStatusFromString(json['status'] as String),
        ownFamilyAmount: json['own_family_amount'] as String,
        generalMaleAmount: json['general_male_amount'] as String,
        generalFemaleAmount: json['general_female_amount'] as String,
        pendingSync: false,
      );

  factory FuneralEvent.fromSqlite(Map<String, dynamic> row) => FuneralEvent(
        id: row['id'] as String,
        deceasedName: row['deceased_name'] as String,
        deceasedGender: row['deceased_gender'] as String,
        deceasedFamilyId: row['deceased_family_id'] as String,
        deceasedFamilyName: row['deceased_family_name'] as String,
        dateOfDeath: DateTime.parse(row['date_of_death'] as String),
        collectionStartDate: DateTime.parse(row['collection_start_date'] as String),
        status: funeralStatusFromString(row['status'] as String),
        ownFamilyAmount: row['own_family_amount'] as String,
        generalMaleAmount: row['general_male_amount'] as String,
        generalFemaleAmount: row['general_female_amount'] as String,
        pendingSync: (row['pending_sync'] as int? ?? 0) == 1,
      );

  Map<String, dynamic> toSqlite() => {
        'id': id,
        'deceased_name': deceasedName,
        'deceased_gender': deceasedGender,
        'deceased_family_id': deceasedFamilyId,
        'deceased_family_name': deceasedFamilyName,
        'date_of_death': dateOfDeath.toIso8601String().substring(0, 10),
        'collection_start_date': collectionStartDate.toIso8601String().substring(0, 10),
        'status': status.name,
        'own_family_amount': ownFamilyAmount,
        'general_male_amount': generalMaleAmount,
        'general_female_amount': generalFemaleAmount,
        'pending_sync': pendingSync ? 1 : 0,
      };
}

enum RateType { ownFamily, general }

RateType rateTypeFromString(String value) => value == 'own_family' ? RateType.ownFamily : RateType.general;

class ContributionObligation {
  final String id;
  final String funeralEventId;
  final String memberId;
  final String memberName;
  final RateType rateType;
  final String expectedAmount;
  final String amountPaid;

  const ContributionObligation({
    required this.id,
    required this.funeralEventId,
    required this.memberId,
    required this.memberName,
    required this.rateType,
    required this.expectedAmount,
    required this.amountPaid,
  });

  double get balance => (double.tryParse(expectedAmount) ?? 0) - (double.tryParse(amountPaid) ?? 0);

  String get paymentStatus {
    final paid = double.tryParse(amountPaid) ?? 0;
    final expected = double.tryParse(expectedAmount) ?? 0;
    if (paid <= 0) return 'unpaid';
    if (paid < expected) return 'partial';
    return 'paid';
  }

  factory ContributionObligation.fromApiJson(Map<String, dynamic> json) => ContributionObligation(
        id: json['id'] as String,
        funeralEventId: json['funeral_event'] as String,
        memberId: (json['member'] as Map<String, dynamic>)['id'] as String,
        memberName: (json['member'] as Map<String, dynamic>)['full_name'] as String,
        rateType: rateTypeFromString(json['rate_type'] as String),
        expectedAmount: json['expected_amount'] as String,
        amountPaid: json['amount_paid'] as String,
      );

  factory ContributionObligation.fromSqlite(Map<String, dynamic> row) => ContributionObligation(
        id: row['id'] as String,
        funeralEventId: row['funeral_event_id'] as String,
        memberId: row['member_id'] as String,
        memberName: row['member_name'] as String,
        rateType: rateTypeFromString(row['rate_type'] as String),
        expectedAmount: row['expected_amount'] as String,
        amountPaid: row['amount_paid'] as String,
      );

  Map<String, dynamic> toSqlite() => {
        'id': id,
        'funeral_event_id': funeralEventId,
        'member_id': memberId,
        'member_name': memberName,
        'rate_type': rateType == RateType.ownFamily ? 'own_family' : 'general',
        'expected_amount': expectedAmount,
        'amount_paid': amountPaid,
      };
}
