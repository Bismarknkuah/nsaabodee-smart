import 'dart:convert';
import 'package:http/http.dart' as http;

import '../domain/funeral_event.dart';

class FuneralsApiException implements Exception {
  final String message;
  FuneralsApiException(this.message);
  @override
  String toString() => message;
}

class FuneralsApiClient {
  final String baseUrl;
  final Future<Map<String, String>> Function() authHeaders;

  FuneralsApiClient({required this.baseUrl, required this.authHeaders});

  Future<List<FuneralEvent>> list({String status = 'active'}) async {
    final headers = await authHeaders();
    final res = await http.get(Uri.parse('$baseUrl/api/funerals/?status=$status'), headers: headers);
    if (res.statusCode >= 400) throw FuneralsApiException('Could not load funerals (${res.statusCode})');
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => FuneralEvent.fromApiJson(e as Map<String, dynamic>)).toList();
  }

  Future<FuneralEvent> create({
    required String deceasedName,
    required String deceasedGender,
    required String deceasedFamilyId,
    required DateTime dateOfDeath,
    required DateTime collectionStartDate,
    String? ownFamilyAmount,
  }) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/funerals/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({
        'deceased_name': deceasedName,
        'deceased_gender': deceasedGender,
        'deceased_family_id': deceasedFamilyId,
        'date_of_death': dateOfDeath.toIso8601String().substring(0, 10),
        'collection_start_date': collectionStartDate.toIso8601String().substring(0, 10),
        if (ownFamilyAmount != null) 'own_family_amount': ownFamilyAmount,
      }),
    );
    if (res.statusCode >= 400) {
      throw FuneralsApiException(jsonDecode(res.body)['detail']?.toString() ?? 'Could not create funeral (${res.statusCode})');
    }
    return FuneralEvent.fromApiJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<List<ContributionObligation>> obligations(String funeralId) async {
    final headers = await authHeaders();
    final res = await http.get(Uri.parse('$baseUrl/api/funerals/$funeralId/obligations/'), headers: headers);
    if (res.statusCode >= 400) throw FuneralsApiException('Could not load ledger (${res.statusCode})');
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => ContributionObligation.fromApiJson(e as Map<String, dynamic>)).toList();
  }

  Future<String> recordPayment({
    required String funeralId,
    required String obligationId,
    required String amount,
    required String method,
    required String clientOpId,
  }) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/funerals/$funeralId/obligations/$obligationId/record-payment/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({'amount': amount, 'method': method, 'client_op_id': clientOpId}),
    );
    if (res.statusCode >= 400) {
      throw FuneralsApiException(jsonDecode(res.body)['detail']?.toString() ?? 'Could not record payment (${res.statusCode})');
    }
    return (jsonDecode(res.body) as Map<String, dynamic>)['id'] as String;
  }

  Future<void> close(String funeralId) async {
    final headers = await authHeaders();
    final res = await http.post(Uri.parse('$baseUrl/api/funerals/$funeralId/close/'), headers: headers);
    if (res.statusCode >= 400) throw FuneralsApiException('Could not close funeral (${res.statusCode})');
  }
}
