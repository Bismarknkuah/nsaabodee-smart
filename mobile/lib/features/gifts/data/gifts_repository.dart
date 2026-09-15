import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:uuid/uuid.dart';

import '../domain/gift_donation.dart';
import 'gifts_api_client.dart';
import 'gifts_local_db.dart';

/// A gift can be recorded offline the same way a family action can: it's
/// written to the local cache immediately, queued, and synced with an
/// idempotent client_op_id so a retried sync never double-records a
/// donation. Unlike funerals, a gift never depends on anything being
/// computed server-side first (there's no fan-out, no rate resolution),
/// so — unlike ContributionObligation payments — a gift CAN be recorded
/// against a funeral that itself hasn't finished syncing yet; it will
/// simply wait in the queue behind that funeral's own create operation.
class GiftsRepository {
  final GiftsLocalDb localDb;
  final GiftsApiClient apiClient;
  final Uuid _uuid = const Uuid();

  GiftsRepository({required this.localDb, required this.apiClient});

  Future<bool> get _isOnline async {
    final result = await Connectivity().checkConnectivity();
    return !result.contains(ConnectivityResult.none);
  }

  Future<List<GiftDonation>> getDonations(String funeralId, {bool forceRefresh = false}) async {
    if (forceRefresh && await _isOnline) {
      try {
        final remote = await apiClient.list(funeralId);
        await localDb.upsertMany(remote);
      } catch (_) {}
    }
    return localDb.listForFuneral(funeralId);
  }

  /// Returns the confirmed donation id if it synced immediately (so the
  /// caller can offer to view/print the receipt right away), or null if
  /// it's still queued for later.
  Future<String?> recordDonation({
    required String funeralId,
    required String donorName,
    String donorPhone = '',
    String amountCash = '0',
    String giftItem = '',
    String? estimatedItemValue,
  }) async {
    final localId = _uuid.v4();
    final clientOpId = _uuid.v4();

    await localDb.upsert(GiftDonation(
      id: localId,
      funeralEventId: funeralId,
      donorName: donorName,
      donorPhone: donorPhone,
      amountCash: amountCash,
      giftItem: giftItem,
      estimatedItemValue: estimatedItemValue,
      receiptNumber: 'PENDING',
      pendingSync: true,
    ));

    await localDb.enqueue(clientOpId, {
      'local_id': localId,
      'funeral_id': funeralId,
      'donor_name': donorName,
      'donor_phone': donorPhone,
      'amount_cash': amountCash,
      'gift_item': giftItem,
      if (estimatedItemValue != null) 'estimated_item_value': estimatedItemValue,
      'client_op_id': clientOpId,
    });

    if (await _isOnline) await syncPendingOps();
    return localDb.getSyncResult(localId);
  }

  Future<void> syncPendingOps() async {
    final ops = await localDb.pendingOps();
    for (final op in ops) {
      final payload = op['payload'] as Map<String, dynamic>;
      try {
        final confirmed = await apiClient.record(
          funeralId: payload['funeral_id'] as String,
          donorName: payload['donor_name'] as String,
          donorPhone: payload['donor_phone'] as String? ?? '',
          amountCash: payload['amount_cash'] as String? ?? '0',
          giftItem: payload['gift_item'] as String? ?? '',
          estimatedItemValue: payload['estimated_item_value'] as String?,
          clientOpId: payload['client_op_id'] as String,
        );
        await localDb.deleteLocal(payload['local_id'] as String);
        await localDb.upsert(confirmed);
        await localDb.setSyncResult(payload['local_id'] as String, confirmed.id);
        await localDb.removeOp(op['op_id'] as String);
      } catch (e) {
        await localDb.markOpFailed(op['op_id'] as String, e.toString());
        break;
      }
    }
  }
}
