import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:uuid/uuid.dart';

import '../domain/funeral_event.dart';
import '../domain/funeral_sync_op.dart';
import 'funerals_api_client.dart';
import 'funerals_local_db.dart';

class PaymentRecordResult {
  final String? error;
  final String? paymentId;
  const PaymentRecordResult._(this.error, this.paymentId);
  factory PaymentRecordResult.error(String message) => PaymentRecordResult._(message, null);
  factory PaymentRecordResult.success(String? paymentId) => PaymentRecordResult._(null, paymentId);
}

/// Same offline-first contract as families_repository.dart: writes apply
/// to the local cache immediately and get queued; the queue flushes when
/// online.
///
/// One important asymmetry vs. the family module: a funeral's ledger
/// (its ContributionObligation rows) is generated SERVER-SIDE at
/// creation, because it depends on every active member's family and
/// gender — data the fan-out needs in bulk, not something a phone should
/// recompute. That means a funeral created while offline has NO
/// obligations to show until it syncs. [recordPayment] refuses to queue
/// a payment against a funeral that's still `pendingSync` for exactly
/// this reason — there being no confirmed obligation to pay against yet
/// isn't a bug, it's the ledger genuinely not existing server-side yet.
class FuneralsRepository {
  final FuneralsLocalDb localDb;
  final FuneralsApiClient apiClient;
  final String communityId;
  final Uuid _uuid = const Uuid();

  FuneralsRepository({required this.localDb, required this.apiClient, required this.communityId});

  Future<bool> get _isOnline async {
    final result = await Connectivity().checkConnectivity();
    return !result.contains(ConnectivityResult.none);
  }

  Future<List<FuneralEvent>> getFunerals({String status = 'active', bool forceRefresh = false}) async {
    if (forceRefresh && await _isOnline) {
      try {
        final remote = await apiClient.list(status: status);
        await localDb.upsertManyFunerals(communityId, remote);
      } catch (_) {
        // Offline-first: a failed refresh just means we show what's cached.
      }
    }
    return localDb.listFunerals(communityId, status: status);
  }

  Future<List<ContributionObligation>> getObligations(String funeralId, {bool forceRefresh = false}) async {
    if (forceRefresh && await _isOnline) {
      try {
        final remote = await apiClient.obligations(funeralId);
        await localDb.upsertManyObligations(communityId, remote);
      } catch (_) {}
    }
    return localDb.listObligations(funeralId);
  }

  Future<FuneralEvent> createFuneral({
    required String deceasedName,
    required String deceasedGender,
    required String deceasedFamilyId,
    required String deceasedFamilyName,
    required DateTime dateOfDeath,
    required DateTime collectionStartDate,
    String? ownFamilyAmount,
  }) async {
    final localId = _uuid.v4();
    final funeral = FuneralEvent(
      id: localId,
      deceasedName: deceasedName,
      deceasedGender: deceasedGender,
      deceasedFamilyId: deceasedFamilyId,
      deceasedFamilyName: deceasedFamilyName,
      dateOfDeath: dateOfDeath,
      collectionStartDate: collectionStartDate,
      status: FuneralStatus.active,
      ownFamilyAmount: ownFamilyAmount ?? '0',
      generalMaleAmount: '0',
      generalFemaleAmount: '0',
      pendingSync: true,
    );
    await localDb.upsertFuneral(communityId, funeral);

    final op = FuneralSyncOp(
      opId: _uuid.v4(),
      type: FuneralSyncOpType.create,
      targetLocalId: localId,
      payload: {
        'deceased_name': deceasedName,
        'deceased_gender': deceasedGender,
        'deceased_family_id': deceasedFamilyId,
        'date_of_death': dateOfDeath.toIso8601String().substring(0, 10),
        'collection_start_date': collectionStartDate.toIso8601String().substring(0, 10),
        'own_family_amount': ownFamilyAmount,
      },
      queuedAt: DateTime.now(),
    );
    await localDb.enqueue(communityId, op);
    if (await _isOnline) await syncPendingOps();
    return funeral;
  }

  /// Returns the confirmed payment id if it synced immediately (so the
  /// caller can offer to show/print the receipt right away), or null if
  /// it's still queued for later — either because the device is offline,
  /// or because an earlier queued op hasn't synced yet. This never
  /// returns an id for a payment that hasn't actually been confirmed by
  /// the server; a null here always means "check back after the next
  /// successful sync," never "assume it worked."
  Future<PaymentRecordResult> recordPayment({
    required FuneralEvent funeral,
    required ContributionObligation obligation,
    required String amount,
    required String method,
  }) async {
    if (funeral.pendingSync) {
      return PaymentRecordResult.error(
        "This funeral hasn't synced to the server yet, so its ledger isn't "
        "confirmed. Connect briefly to sync it before recording payments.",
      );
    }

    await localDb.recordLocalPayment(obligation.id, double.parse(amount));

    final clientOpId = _uuid.v4();
    final op = FuneralSyncOp(
      opId: clientOpId,
      type: FuneralSyncOpType.recordPayment,
      targetLocalId: obligation.id,
      payload: {
        'funeral_id': funeral.id,
        'obligation_id': obligation.id,
        'amount': amount,
        'method': method,
        'client_op_id': clientOpId,
      },
      queuedAt: DateTime.now(),
    );
    await localDb.enqueue(communityId, op);
    if (await _isOnline) await syncPendingOps();

    final paymentId = await localDb.getLastSyncedPaymentId(obligation.id);
    return PaymentRecordResult.success(paymentId);
  }

  Future<void> closeFuneral(FuneralEvent funeral) async {
    final op = FuneralSyncOp(
      opId: _uuid.v4(),
      type: FuneralSyncOpType.close,
      targetLocalId: funeral.id,
      payload: {'funeral_id': funeral.id},
      queuedAt: DateTime.now(),
    );
    await localDb.enqueue(communityId, op);
    if (await _isOnline) await syncPendingOps();
  }

  Future<void> syncPendingOps() async {
    final ops = await localDb.pendingOps(communityId);
    for (final op in ops) {
      try {
        await _applyRemote(op);
        await localDb.removeOp(op.opId);
      } catch (e) {
        await localDb.markOpFailed(op.opId, e.toString());
        break; // preserve ordering — a payment op may depend on its funeral's create op having landed first
      }
    }
  }

  Future<void> _applyRemote(FuneralSyncOp op) async {
    switch (op.type) {
      case FuneralSyncOpType.create:
        final created = await apiClient.create(
          deceasedName: op.payload['deceased_name'] as String,
          deceasedGender: op.payload['deceased_gender'] as String,
          deceasedFamilyId: op.payload['deceased_family_id'] as String,
          dateOfDeath: DateTime.parse(op.payload['date_of_death'] as String),
          collectionStartDate: DateTime.parse(op.payload['collection_start_date'] as String),
          ownFamilyAmount: op.payload['own_family_amount'] as String?,
        );
        // The server assigns the real id; drop the local placeholder row
        // (keyed on the client-generated id) and store the confirmed one
        // so future payments target the id the server actually knows.
        await localDb.deleteFuneral(communityId, op.targetLocalId);
        await localDb.upsertFuneral(communityId, created);
        break;
      case FuneralSyncOpType.recordPayment:
        final paymentId = await apiClient.recordPayment(
          funeralId: op.payload['funeral_id'] as String,
          obligationId: op.payload['obligation_id'] as String,
          amount: op.payload['amount'] as String,
          method: op.payload['method'] as String,
          clientOpId: op.payload['client_op_id'] as String,
        );
        await localDb.setLastSyncedPaymentId(op.payload['obligation_id'] as String, paymentId);
        break;
      case FuneralSyncOpType.close:
        await apiClient.close(op.payload['funeral_id'] as String);
        break;
    }
  }
}
