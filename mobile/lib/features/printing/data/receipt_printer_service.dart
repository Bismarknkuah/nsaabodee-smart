import '../domain/receipt_escpos_content.dart';
import 'printer_preferences_local_db.dart';
import 'thermal_printer_connection.dart';

class NoPrinterConfiguredException implements Exception {
  @override
  String toString() => 'No printer has been set up on this device yet.';
}

/// The single entry point the UI calls to physically print a receipt.
/// On success, it also tells the backend the physical slip was actually
/// handed over (`markPrinted`), which is what powers the "everyone who
/// paid in cash has a confirmed physical receipt, or doesn't yet"
/// dashboard (`reports.services.unprinted_receipts` — see the backend
/// pass this came from). If printing fails partway through, `markPrinted`
/// is deliberately never called, so a jammed printer correctly leaves
/// that payment showing as still needing a reprint rather than falsely
/// marked done.
class ReceiptPrinterService {
  final PrinterPreferencesLocalDb preferencesDb;
  final Future<void> Function(String paymentId) markContributionPrinted;
  final Future<void> Function(String donationId) markGiftPrinted;

  ReceiptPrinterService({
    required this.preferencesDb,
    required this.markContributionPrinted,
    required this.markGiftPrinted,
  });

  Future<ThermalPrinterConnection> _resolveConnection() async {
    final pref = await preferencesDb.get();
    if (pref == null) throw NoPrinterConfiguredException();

    if (pref.kind == PrinterKind.network) {
      final parts = pref.address.split(':');
      final host = parts.first;
      final port = parts.length > 1 ? int.tryParse(parts[1]) ?? 9100 : 9100;
      return NetworkThermalPrinterConnection(host: host, port: port);
    }
    return BluetoothThermalPrinterConnection(deviceAddress: pref.address);
  }

  Future<void> printContributionReceipt({
    required Map<String, dynamic> receiptData,
    required String communityName,
    required String paymentId,
  }) async {
    final bytes = ReceiptEscPosContent.contribution(receiptData, communityName);
    final connection = await _resolveConnection();
    await connection.connect();
    try {
      await connection.write(bytes);
    } finally {
      await connection.disconnect();
    }
    await markContributionPrinted(paymentId);
  }

  Future<void> printGiftReceipt({
    required Map<String, dynamic> receiptData,
    required String communityName,
    required String donationId,
  }) async {
    final bytes = ReceiptEscPosContent.gift(receiptData, communityName);
    final connection = await _resolveConnection();
    await connection.connect();
    try {
      await connection.write(bytes);
    } finally {
      await connection.disconnect();
    }
    await markGiftPrinted(donationId);
  }
}
