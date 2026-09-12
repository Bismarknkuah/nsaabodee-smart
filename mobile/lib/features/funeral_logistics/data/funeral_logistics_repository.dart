import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:uuid/uuid.dart';

import '../domain/funeral_logistics_models.dart';
import 'funeral_logistics_api_client.dart';
import 'funeral_logistics_local_db.dart';

/// Same offline-first contract as every other repository in this app:
/// write locally first, queue the op, flush when connectivity returns.
///
/// Attendance has one deliberate asymmetry from every other queued write
/// here: it carries no client_op_id, because the backend's
/// `record_attendance` is already idempotent on (funeral, member) by
/// construction — checking the same member in twice is a documented
/// no-op server-side, not an error, so there's nothing for a client id
/// to protect against. A duplicate guest-name entry is low-stakes (it's
/// just a name in an attendance log, not money), so it isn't worth the
/// complexity either.
class FuneralLogisticsRepository {
  final FuneralLogisticsLocalDb localDb;
  final FuneralLogisticsApiClient apiClient;
  final Uuid _uuid = const Uuid();

  FuneralLogisticsRepository({required this.localDb, required this.apiClient});

  Future<bool> get _isOnline async {
    final result = await Connectivity().checkConnectivity();
    return !result.contains(ConnectivityResult.none);
  }

  Future<List<FuneralExpense>> getExpenses(String funeralId, {bool forceRefresh = false}) async {
    if (forceRefresh && await _isOnline) {
      try {
        final remote = await apiClient.listExpenses(funeralId);
        await localDb.upsertManyExpenses(remote);
      } catch (_) {}
    }
    return localDb.listExpenses(funeralId);
  }

  Future<void> recordExpense({
    required String funeralId,
    required String description,
    required String category,
    required String amount,
    required String paymentMethod,
    required String incurredOn,
  }) async {
    final localId = _uuid.v4();
    final clientOpId = _uuid.v4();

    await localDb.upsertExpense(FuneralExpense(
      id: localId,
      funeralEventId: funeralId,
      description: description,
      category: category,
      amount: amount,
      paymentMethod: paymentMethod,
      voucherNumber: 'PENDING',
      incurredOn: incurredOn,
      pendingSync: true,
    ));

    await localDb.enqueue(clientOpId, 'expense', localId, {
      'funeral_id': funeralId,
      'description': description,
      'category': category,
      'amount': amount,
      'payment_method': paymentMethod,
      'incurred_on': incurredOn,
      'client_op_id': clientOpId,
    });

    if (await _isOnline) await syncPendingOps();
  }

  Future<List<FuneralAttendanceRecord>> getAttendance(String funeralId, {bool forceRefresh = false}) async {
    if (forceRefresh && await _isOnline) {
      try {
        final remote = await apiClient.listAttendance(funeralId);
        await localDb.upsertManyAttendance(remote);
      } catch (_) {}
    }
    return localDb.listAttendance(funeralId);
  }

  Future<void> recordAttendance({
    required String funeralId,
    String? memberId,
    String? memberName,
    String guestName = '',
  }) async {
    final localId = _uuid.v4();
    final opId = _uuid.v4();

    await localDb.upsertAttendance(FuneralAttendanceRecord(
      id: localId,
      funeralEventId: funeralId,
      memberId: memberId,
      displayName: memberId != null ? (memberName ?? 'Member') : guestName,
      pendingSync: true,
    ));

    await localDb.enqueue(opId, 'attendance', localId, {
      'funeral_id': funeralId,
      'member_id': memberId,
      'guest_name': guestName,
    });

    if (await _isOnline) await syncPendingOps();
  }

  Future<void> syncPendingOps() async {
    final ops = await localDb.pendingOps();
    for (final op in ops) {
      final payload = op['payload'] as Map<String, dynamic>;
      final localId = op['local_id'] as String;
      try {
        if (op['kind'] == 'expense') {
          final confirmed = await apiClient.recordExpense(
            funeralId: payload['funeral_id'] as String,
            description: payload['description'] as String,
            category: payload['category'] as String,
            amount: payload['amount'] as String,
            paymentMethod: payload['payment_method'] as String,
            incurredOn: payload['incurred_on'] as String,
            clientOpId: payload['client_op_id'] as String,
          );
          await localDb.deleteExpenseLocal(localId);
          await localDb.upsertExpense(confirmed);
        } else {
          final confirmed = await apiClient.recordAttendance(
            funeralId: payload['funeral_id'] as String,
            memberId: payload['member_id'] as String?,
            guestName: payload['guest_name'] as String? ?? '',
          );
          await localDb.deleteAttendanceLocal(localId);
          await localDb.upsertAttendance(confirmed);
        }
        await localDb.removeOp(op['op_id'] as String);
      } catch (e) {
        await localDb.markOpFailed(op['op_id'] as String, e.toString());
        break;
      }
    }
  }
}
