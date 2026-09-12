import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:uuid/uuid.dart';

import '../domain/family.dart';
import '../domain/family_sync_op.dart';
import 'families_api_client.dart';
import 'families_local_db.dart';

/// Every write (add / rename / merge / deactivate / delete / transfer /
/// assign-head) works identically whether the collector is online or not:
///
///   1. Apply the change to the local SQLite cache immediately, so the UI
///      updates instantly and the app keeps working offline.
///   2. Enqueue a [FamilySyncOp] describing the change.
///   3. If a connection is available right now, try to flush the queue
///      immediately; otherwise leave it for [syncPendingOps] to pick up
///      the next time connectivity returns (call this from a
///      connectivity-change listener or a periodic background task).
///
/// The server is always the source of truth for `member_count`,
/// `family_head`, and merge outcomes — after any successful sync, the
/// local row is overwritten with what the server returned.
class FamiliesRepository {
  final FamiliesLocalDb localDb;
  final FamiliesApiClient apiClient;
  final String communityId;
  final Uuid _uuid = const Uuid();

  FamiliesRepository({
    required this.localDb,
    required this.apiClient,
    required this.communityId,
  });

  Future<bool> get _isOnline async {
    final result = await Connectivity().checkConnectivity();
    return !result.contains(ConnectivityResult.none);
  }

  Future<List<Family>> getFamilies({bool includeInactive = false, bool forceRefresh = false}) async {
    if (forceRefresh && await _isOnline) {
      try {
        final remote = await apiClient.list(includeInactive: includeInactive);
        await localDb.upsertMany(communityId, remote);
      } catch (_) {
        // Fall through to whatever is cached locally — offline-first means
        // a failed refresh is never a fatal error for the screen.
      }
    }
    return localDb.listFamilies(communityId, includeInactive: includeInactive);
  }

  Future<void> addFamily({required String name, String description = ''}) async {
    final localId = _uuid.v4();
    await localDb.upsertFamily(
      communityId,
      Family(
        id: localId,
        name: name,
        description: description,
        status: FamilyStatus.active,
        memberCount: 0,
        updatedAt: DateTime.now(),
        pendingSync: true,
      ),
    );
    await _queueAndTrySync(FamilySyncOpType.create, localId, {'name': name, 'description': description});
  }

  Future<void> renameFamily(Family family, String newName) async {
    await localDb.upsertFamily(communityId, family.copyWith(name: newName, pendingSync: true));
    await _queueAndTrySync(FamilySyncOpType.rename, family.id, {'name': newName});
  }

  Future<void> deactivateFamily(Family family) async {
    await localDb.upsertFamily(
      communityId,
      family.copyWith(status: FamilyStatus.deactivated, pendingSync: true),
    );
    await _queueAndTrySync(FamilySyncOpType.deactivate, family.id, {});
  }

  Future<void> reactivateFamily(Family family) async {
    await localDb.upsertFamily(
      communityId,
      family.copyWith(status: FamilyStatus.active, pendingSync: true),
    );
    await _queueAndTrySync(FamilySyncOpType.reactivate, family.id, {});
  }

  Future<void> deleteFamily(Family family, {bool force = false}) async {
    await localDb.upsertFamily(
      communityId,
      family.copyWith(status: FamilyStatus.deleted, pendingSync: true),
    );
    await _queueAndTrySync(FamilySyncOpType.delete, family.id, {'force': force});
  }

  Future<void> mergeFamilies({required Family source, required Family target}) async {
    await localDb.upsertFamily(
      communityId,
      source.copyWith(status: FamilyStatus.merged, mergedIntoId: target.id, pendingSync: true),
    );
    await _queueAndTrySync(FamilySyncOpType.merge, source.id, {'target_family_id': target.id});
  }

  Future<void> transferMembers({required Family targetFamily, required List<String> memberIds}) async {
    await _queueAndTrySync(
      FamilySyncOpType.transferMembers,
      targetFamily.id,
      {'member_ids': memberIds, 'target_family_id': targetFamily.id},
    );
  }

  Future<void> assignHead(Family family, String memberId) async {
    await _queueAndTrySync(FamilySyncOpType.assignHead, family.id, {'member_id': memberId});
  }

  Future<void> _queueAndTrySync(
    FamilySyncOpType type,
    String familyLocalId,
    Map<String, dynamic> payload,
  ) async {
    final op = FamilySyncOp(
      opId: _uuid.v4(),
      type: type,
      familyLocalId: familyLocalId,
      payload: payload,
      queuedAt: DateTime.now(),
    );
    await localDb.enqueue(communityId, op);
    if (await _isOnline) {
      await syncPendingOps();
    }
  }

  /// Flush every queued operation in order. Safe to call repeatedly (e.g.
  /// from a connectivity-restored listener) — already-applied ops are
  /// removed from the queue as soon as the server confirms them, so a
  /// duplicate call simply finds nothing left to do.
  Future<void> syncPendingOps() async {
    final ops = await localDb.pendingOps(communityId);
    for (final op in ops) {
      try {
        final updated = await _applyRemote(op);
        if (updated != null) {
          await localDb.upsertFamily(communityId, updated);
        }
        await localDb.removeOp(op.opId);
      } catch (e) {
        await localDb.markOpFailed(op.opId, e.toString());
        // Stop on first failure to preserve ordering — a later op (e.g. a
        // transfer into a family) may depend on an earlier one (e.g. that
        // family's creation) having already landed on the server.
        break;
      }
    }
  }

  Future<Family?> _applyRemote(FamilySyncOp op) async {
    switch (op.type) {
      case FamilySyncOpType.create:
        return apiClient.create(
          name: op.payload['name'] as String,
          description: op.payload['description'] as String? ?? '',
        );
      case FamilySyncOpType.rename:
        return apiClient.rename(op.familyLocalId, op.payload['name'] as String);
      case FamilySyncOpType.merge:
        return apiClient.merge(op.familyLocalId, op.payload['target_family_id'] as String);
      case FamilySyncOpType.deactivate:
        return apiClient.deactivate(op.familyLocalId);
      case FamilySyncOpType.reactivate:
        return apiClient.reactivate(op.familyLocalId);
      case FamilySyncOpType.delete:
        await apiClient.delete(op.familyLocalId, force: op.payload['force'] as bool? ?? false);
        return null;
      case FamilySyncOpType.transferMembers:
        final memberIds = (op.payload['member_ids'] as List<dynamic>).cast<String>();
        return apiClient.transferMembers(op.payload['target_family_id'] as String, memberIds);
      case FamilySyncOpType.assignHead:
        return apiClient.assignHead(op.familyLocalId, op.payload['member_id'] as String);
    }
  }
}
