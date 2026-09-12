enum FamilyStatus { active, deactivated, merged, deleted }

FamilyStatus familyStatusFromString(String value) {
  switch (value) {
    case 'active':
      return FamilyStatus.active;
    case 'deactivated':
      return FamilyStatus.deactivated;
    case 'merged':
      return FamilyStatus.merged;
    case 'deleted':
      return FamilyStatus.deleted;
    default:
      throw ArgumentError('Unknown family status: $value');
  }
}

String familyStatusToString(FamilyStatus status) => status.name;

class Family {
  final String id;
  final String name;
  final String description;
  final FamilyStatus status;
  final String? familyHeadId;
  final String? familyHeadName;
  final int memberCount;
  final String? mergedIntoId;
  final DateTime updatedAt;

  /// True while this record exists only locally and has not yet been
  /// confirmed by the server (i.e. it is sitting in the sync queue).
  final bool pendingSync;

  const Family({
    required this.id,
    required this.name,
    required this.description,
    required this.status,
    required this.memberCount,
    required this.updatedAt,
    this.familyHeadId,
    this.familyHeadName,
    this.mergedIntoId,
    this.pendingSync = false,
  });

  Family copyWith({
    String? name,
    String? description,
    FamilyStatus? status,
    String? familyHeadId,
    String? familyHeadName,
    int? memberCount,
    String? mergedIntoId,
    DateTime? updatedAt,
    bool? pendingSync,
  }) {
    return Family(
      id: id,
      name: name ?? this.name,
      description: description ?? this.description,
      status: status ?? this.status,
      familyHeadId: familyHeadId ?? this.familyHeadId,
      familyHeadName: familyHeadName ?? this.familyHeadName,
      memberCount: memberCount ?? this.memberCount,
      mergedIntoId: mergedIntoId ?? this.mergedIntoId,
      updatedAt: updatedAt ?? this.updatedAt,
      pendingSync: pendingSync ?? this.pendingSync,
    );
  }

  factory Family.fromApiJson(Map<String, dynamic> json) {
    final head = json['family_head'] as Map<String, dynamic>?;
    return Family(
      id: json['id'] as String,
      name: json['name'] as String,
      description: (json['description'] as String?) ?? '',
      status: familyStatusFromString(json['status'] as String),
      familyHeadId: head?['id'] as String?,
      familyHeadName: head?['full_name'] as String?,
      memberCount: json['member_count'] as int? ?? 0,
      mergedIntoId: json['merged_into'] as String?,
      updatedAt: DateTime.parse(json['updated_at'] as String),
      pendingSync: false,
    );
  }

  factory Family.fromSqlite(Map<String, dynamic> row) {
    return Family(
      id: row['id'] as String,
      name: row['name'] as String,
      description: row['description'] as String? ?? '',
      status: familyStatusFromString(row['status'] as String),
      familyHeadId: row['family_head_id'] as String?,
      familyHeadName: row['family_head_name'] as String?,
      memberCount: row['member_count'] as int? ?? 0,
      mergedIntoId: row['merged_into_id'] as String?,
      updatedAt: DateTime.parse(row['updated_at'] as String),
      pendingSync: (row['pending_sync'] as int? ?? 0) == 1,
    );
  }

  Map<String, dynamic> toSqlite() => {
        'id': id,
        'name': name,
        'description': description,
        'status': familyStatusToString(status),
        'family_head_id': familyHeadId,
        'family_head_name': familyHeadName,
        'member_count': memberCount,
        'merged_into_id': mergedIntoId,
        'updated_at': updatedAt.toIso8601String(),
        'pending_sync': pendingSync ? 1 : 0,
      };
}
