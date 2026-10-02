import 'dart:convert';
import 'package:http/http.dart' as http;

import '../domain/funeral_logistics_models.dart';

class FuneralLogisticsApiException implements Exception {
  final String message;
  FuneralLogisticsApiException(this.message);
  @override
  String toString() => message;
}

class FuneralLogisticsApiClient {
  final String baseUrl;
  final Future<Map<String, String>> Function() authHeaders;

  FuneralLogisticsApiClient({required this.baseUrl, required this.authHeaders});

  Future<List<FuneralExpense>> listExpenses(String funeralId) async {
    final headers = await authHeaders();
    final res = await http.get(Uri.parse('$baseUrl/api/funerals/$funeralId/expenses/'), headers: headers);
    if (res.statusCode >= 400) throw FuneralLogisticsApiException('Could not load expenses (${res.statusCode})');
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => FuneralExpense.fromApiJson(e as Map<String, dynamic>)).toList();
  }

  Future<FuneralExpense> recordExpense({
    required String funeralId,
    required String description,
    required String category,
    required String amount,
    required String paymentMethod,
    required String incurredOn,
    required String clientOpId,
  }) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/funerals/$funeralId/expenses/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({
        'description': description,
        'category': category,
        'amount': amount,
        'payment_method': paymentMethod,
        'incurred_on': incurredOn,
        'client_op_id': clientOpId,
      }),
    );
    if (res.statusCode >= 400) {
      throw FuneralLogisticsApiException(jsonDecode(res.body)['detail']?.toString() ?? 'Could not record expense (${res.statusCode})');
    }
    return FuneralExpense.fromApiJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<List<FuneralAttendanceRecord>> listAttendance(String funeralId) async {
    final headers = await authHeaders();
    final res = await http.get(Uri.parse('$baseUrl/api/funerals/$funeralId/attendance/'), headers: headers);
    if (res.statusCode >= 400) throw FuneralLogisticsApiException('Could not load attendance (${res.statusCode})');
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => FuneralAttendanceRecord.fromApiJson(e as Map<String, dynamic>)).toList();
  }

  Future<FuneralAttendanceRecord> recordAttendance({
    required String funeralId,
    String? memberId,
    String guestName = '',
  }) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/funerals/$funeralId/attendance/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({if (memberId != null) 'member_id': memberId, 'guest_name': guestName}),
    );
    if (res.statusCode >= 400) {
      throw FuneralLogisticsApiException(jsonDecode(res.body)['detail']?.toString() ?? 'Could not record attendance (${res.statusCode})');
    }
    return FuneralAttendanceRecord.fromApiJson(jsonDecode(res.body) as Map<String, dynamic>);
  }
}
