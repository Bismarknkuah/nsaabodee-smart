import 'dart:convert';
import 'package:http/http.dart' as http;

import '../domain/gift_donation.dart';

class GiftsApiException implements Exception {
  final String message;
  GiftsApiException(this.message);
  @override
  String toString() => message;
}

class GiftsApiClient {
  final String baseUrl;
  final Future<Map<String, String>> Function() authHeaders;

  GiftsApiClient({required this.baseUrl, required this.authHeaders});

  Future<List<GiftDonation>> list(String funeralId) async {
    final headers = await authHeaders();
    final res = await http.get(Uri.parse('$baseUrl/api/funerals/$funeralId/gifts/'), headers: headers);
    if (res.statusCode >= 400) throw GiftsApiException('Could not load gift ledger (${res.statusCode})');
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.map((e) => GiftDonation.fromApiJson(e as Map<String, dynamic>)).toList();
  }

  Future<GiftDonation> record({
    required String funeralId,
    required String donorName,
    String donorPhone = '',
    String amountCash = '0',
    String giftItem = '',
    String? estimatedItemValue,
    required String clientOpId,
  }) async {
    final headers = await authHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/funerals/$funeralId/gifts/'),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode({
        'donor_name': donorName,
        'donor_phone': donorPhone,
        'amount_cash': amountCash,
        'gift_item': giftItem,
        if (estimatedItemValue != null) 'estimated_item_value': estimatedItemValue,
        'client_op_id': clientOpId,
      }),
    );
    if (res.statusCode >= 400) {
      throw GiftsApiException(jsonDecode(res.body)['detail']?.toString() ?? 'Could not record gift (${res.statusCode})');
    }
    return GiftDonation.fromApiJson(jsonDecode(res.body) as Map<String, dynamic>);
  }
}
