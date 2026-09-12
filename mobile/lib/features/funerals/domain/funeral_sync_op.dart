import 'dart:convert';

enum FuneralSyncOpType { create, close, recordPayment }

/// Mirrors families/domain/family_sync_op.dart's pattern exactly: every
/// offline write becomes one of these, keyed by a client-generated
/// [opId]/[clientOpId] so a retried sync after a dropped connection can
/// never double-apply — critical here specifically because a duplicated
/// "recordPayment" would mean double-charging a grieving family member,
/// not just a cosmetic glitch.
class FuneralSyncOp {
  final String opId;
  final FuneralSyncOpType type;
  final String targetLocalId; // funeral id, or obligation id for payments
  final Map<String, dynamic> payload;
  final DateTime queuedAt;
  int attempts;
  String? lastError;

  FuneralSyncOp({
    required this.opId,
    required this.type,
    required this.targetLocalId,
    required this.payload,
    required this.queuedAt,
    this.attempts = 0,
    this.lastError,
  });

  Map<String, dynamic> toSqlite() => {
        'op_id': opId,
        'type': type.name,
        'target_local_id': targetLocalId,
        'payload': jsonEncode(payload),
        'queued_at': queuedAt.toIso8601String(),
        'attempts': attempts,
        'last_error': lastError,
      };

  factory FuneralSyncOp.fromSqlite(Map<String, dynamic> row) => FuneralSyncOp(
        opId: row['op_id'] as String,
        type: FuneralSyncOpType.values.byName(row['type'] as String),
        targetLocalId: row['target_local_id'] as String,
        payload: jsonDecode(row['payload'] as String) as Map<String, dynamic>,
        queuedAt: DateTime.parse(row['queued_at'] as String),
        attempts: row['attempts'] as int? ?? 0,
        lastError: row['last_error'] as String?,
      );
}
