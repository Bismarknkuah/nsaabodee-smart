import 'dart:convert';

enum FamilySyncOpType {
  create,
  rename,
  merge,
  deactivate,
  reactivate,
  delete,
  transferMembers,
  assignHead,
}

/// One queued write against the Family Management API. Collectors and
/// administrators can perform every family action offline; each action
/// becomes a row here with a client-generated [opId] used to make the
/// eventual sync idempotent (the server-side sync endpoint deduplicates
/// on this id, so a retried request after a dropped connection can never
/// double-apply).
class FamilySyncOp {
  final String opId;
  final FamilySyncOpType type;
  final String familyLocalId;
  final Map<String, dynamic> payload;
  final DateTime queuedAt;
  int attempts;
  String? lastError;

  FamilySyncOp({
    required this.opId,
    required this.type,
    required this.familyLocalId,
    required this.payload,
    required this.queuedAt,
    this.attempts = 0,
    this.lastError,
  });

  Map<String, dynamic> toSqlite() => {
        'op_id': opId,
        'type': type.name,
        'family_local_id': familyLocalId,
        'payload': jsonEncode(payload),
        'queued_at': queuedAt.toIso8601String(),
        'attempts': attempts,
        'last_error': lastError,
      };

  factory FamilySyncOp.fromSqlite(Map<String, dynamic> row) => FamilySyncOp(
        opId: row['op_id'] as String,
        type: FamilySyncOpType.values.byName(row['type'] as String),
        familyLocalId: row['family_local_id'] as String,
        payload: jsonDecode(row['payload'] as String) as Map<String, dynamic>,
        queuedAt: DateTime.parse(row['queued_at'] as String),
        attempts: row['attempts'] as int? ?? 0,
        lastError: row['last_error'] as String?,
      );
}
