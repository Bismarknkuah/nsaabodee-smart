import 'dart:convert';

import 'package:http/http.dart' as http;

import '../domain/member.dart';

class MembersApiException implements Exception {
  final String message;
  MembersApiException(this.message);
  @override
  String toString() => message;
}

class MembersApiClient {
  final String baseUrl;
  final Future<Map<String, String>> Function() authHeaders;

  MembersApiClient({required this.baseUrl, required this.authHeaders});

  Future<List<Member>> search(String query) async {
    final headers = await authHeaders();
    final res = await http.get(Uri.parse('$baseUrl/api/members/?search=${Uri.encodeQueryComponent(query)}'), headers: headers);
    if (res.statusCode >= 400) throw MembersApiException('Could not search members (${res.statusCode})');
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => Member.fromApiJson(e as Map<String, dynamic>)).toList();
  }

  /// Registers a member. [photoFilePath] is optional — if the collector
  /// captured a photo offline, its local file path is uploaded as
  /// multipart form data once a connection is available; if null, the
  /// member is registered without a photo (one can be added later).
  Future<Member> register({
    required String fullName,
    required String gender,
    String? familyId,
    String phone = '',
    String? ghanaCardNumber,
    String? photoFilePath,
  }) async {
    final headers = await authHeaders();
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/api/members/'));
    request.headers.addAll(headers);
    request.fields['full_name'] = fullName;
    request.fields['gender'] = gender;
    if (familyId != null) request.fields['family_id'] = familyId;
    if (phone.isNotEmpty) request.fields['phone'] = phone;
    if (ghanaCardNumber != null && ghanaCardNumber.isNotEmpty) {
      request.fields['ghana_card_number'] = ghanaCardNumber;
    }
    if (photoFilePath != null) {
      request.files.add(await http.MultipartFile.fromPath('photo', photoFilePath));
    }

    final streamed = await request.send();
    final res = await http.Response.fromStream(streamed);
    if (res.statusCode >= 400) {
      throw MembersApiException(jsonDecode(res.body)['detail']?.toString() ?? 'Could not register member (${res.statusCode})');
    }
    return Member.fromApiJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<Map<String, dynamic>> card(String memberId) async {
    final headers = await authHeaders();
    final res = await http.get(Uri.parse('$baseUrl/api/members/$memberId/card/'), headers: headers);
    if (res.statusCode >= 400) throw MembersApiException('Could not load membership card (${res.statusCode})');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
