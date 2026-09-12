import 'dart:convert';
import 'package:http/http.dart' as http;

import '../domain/family.dart';

class FamiliesApiException implements Exception {
  final String message;
  FamiliesApiException(this.message);
  @override
  String toString() => message;
}

class FamiliesApiClient {
  final String baseUrl;
  final Future<Map<String, String>> Function() authHeaders;

  FamiliesApiClient({required this.baseUrl, required this.authHeaders});

  Future<Map<String, dynamic>> _decode(http.Response res) async {
    final body = res.body.isNotEmpty ? jsonDecode(res.body) : {};
    if (res.statusCode >= 400) {
      final message = body is Map && body['detail'] != null
          ? body['detail'].toString()
          : 'Request failed (${res.statusCode})';
      throw FamiliesApiException(message);
    }
    return body is Map<String, dynamic> ? body : {};
  }

  Future<List<Family>> list({bool includeInactive = false}) async {
    final headers = await authHeaders();
    final res = await http.get(
      Uri.parse('$baseUrl/api/families/?include_inactive=$includeInactive'),
      headers: headers,
    );
    if (res.statusCode >= 400) throw FamiliesApiException('Could not load families (${res.statusCode})');
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => Family.fromApiJson(e as Map<String, dynamic>)).toList();
  }

  Future<Family> create({required String name, String description = ''}) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/families/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'description': description}),
    );
    return Family.fromApiJson(await _decode(res));
  }

  Future<Family> rename(String id, String name) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/families/$id/rename/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({'name': name}),
    );
    return Family.fromApiJson(await _decode(res));
  }

  Future<Family> merge(String sourceId, String targetId) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/families/$sourceId/merge/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({'target_family_id': targetId}),
    );
    return Family.fromApiJson(await _decode(res));
  }

  Future<Family> deactivate(String id) async {
    final headers = await authHeaders();
    final res = await http.post(Uri.parse('$baseUrl/api/families/$id/deactivate/'), headers: headers);
    return Family.fromApiJson(await _decode(res));
  }

  Future<Family> reactivate(String id) async {
    final headers = await authHeaders();
    final res = await http.post(Uri.parse('$baseUrl/api/families/$id/reactivate/'), headers: headers);
    return Family.fromApiJson(await _decode(res));
  }

  Future<void> delete(String id, {bool force = false}) async {
    final headers = await authHeaders();
    final res = await http.delete(
      Uri.parse('$baseUrl/api/families/$id/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({'force': force}),
    );
    if (res.statusCode >= 400) throw FamiliesApiException('Could not delete family (${res.statusCode})');
  }

  Future<Family> transferMembers(String targetId, List<String> memberIds) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/families/$targetId/transfer-members/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({'member_ids': memberIds, 'target_family_id': targetId}),
    );
    return Family.fromApiJson(await _decode(res));
  }

  Future<Family> assignHead(String id, String memberId) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/families/$id/assign-head/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({'member_id': memberId}),
    );
    return Family.fromApiJson(await _decode(res));
  }
}
