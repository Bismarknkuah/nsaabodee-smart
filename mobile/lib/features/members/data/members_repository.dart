import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:uuid/uuid.dart';

import '../domain/member.dart';
import 'members_api_client.dart';
import 'members_local_db.dart';

/// Registration works fully offline, matching the master brief's
/// requirement that collectors register members without internet. A
/// membership number can't be assigned locally the way it is server-side
/// (it has to be unique per community, checked against everyone else's
/// pending registrations too) — so an offline registration shows
/// "Pending" as its membership number until sync confirms the real one.
/// The photo is the same story: captured to a local file path
/// immediately, uploaded as multipart form data the moment sync runs.
class MembersRepository {
  final MembersLocalDb localDb;
  final MembersApiClient apiClient;
  final String communityId;
  final Uuid _uuid = const Uuid();

  MembersRepository({required this.localDb, required this.apiClient, required this.communityId});

  Future<bool> get _isOnline async {
    final result = await Connectivity().checkConnectivity();
    return !result.contains(ConnectivityResult.none);
  }

  Future<List<Member>> search({String query = '', bool forceRefresh = false}) async {
    if (forceRefresh && await _isOnline && query.isNotEmpty) {
      try {
        final remote = await apiClient.search(query);
        await localDb.upsertMany(communityId, remote);
      } catch (_) {}
    }
    return localDb.search(communityId, query: query);
  }

  Future<Member> registerMember({
    required String fullName,
    required String gender,
    String? familyId,
    String? familyName,
    String phone = '',
    String? ghanaCardNumber,
    String? photoLocalPath,
  }) async {
    final localId = _uuid.v4();
    final member = Member(
      id: localId,
      membershipNumber: 'PENDING',
      fullName: fullName,
      gender: gender,
      familyId: familyId,
      familyName: familyName,
      phone: phone,
      status: 'active',
      defaulterTier: 'none',
      pendingPhotoLocalPath: photoLocalPath,
      pendingSync: true,
    );
    await localDb.upsert(communityId, member);

    final opId = _uuid.v4();
    await localDb.enqueue(communityId, opId, localId, {
      'full_name': fullName,
      'gender': gender,
      'family_id': familyId,
      'phone': phone,
      'ghana_card_number': ghanaCardNumber,
      'photo_local_path': photoLocalPath,
    });

    if (await _isOnline) await syncPendingOps();
    return member;
  }

  Future<void> syncPendingOps() async {
    final ops = await localDb.pendingOps(communityId);
    for (final op in ops) {
      final payload = op['payload'] as Map<String, dynamic>;
      final localId = op['local_id'] as String;
      try {
        final confirmed = await apiClient.register(
          fullName: payload['full_name'] as String,
          gender: payload['gender'] as String,
          familyId: payload['family_id'] as String?,
          phone: payload['phone'] as String? ?? '',
          ghanaCardNumber: payload['ghana_card_number'] as String?,
          photoFilePath: payload['photo_local_path'] as String?,
        );
        await localDb.deleteLocal(communityId, localId);
        await localDb.upsert(communityId, confirmed);
        await localDb.removeOp(op['op_id'] as String);
      } catch (e) {
        await localDb.markOpFailed(op['op_id'] as String, e.toString());
        break;
      }
    }
  }
}
