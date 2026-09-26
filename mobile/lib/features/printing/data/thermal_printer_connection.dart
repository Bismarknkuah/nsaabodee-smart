import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

/// A destination a receipt's ESC/POS bytes can be sent to. Two real,
/// independent transports are supported — a thermal printer only needs
/// ONE of them, whichever it actually has:
///
///   - [NetworkThermalPrinterConnection]: nearly every "WiFi" or
///     "Ethernet" thermal printer listens for raw ESC/POS bytes on a
///     plain TCP socket, port 9100, by long-standing convention (the
///     same port used for generic "raw" printing to network printers
///     generally). This needs no special package — `dart:io`'s `Socket`
///     is the entire implementation — which is why it's the transport
///     I'm most confident is correct without hardware to test against.
///
///   - [BluetoothThermalPrinterConnection]: classic (non-BLE) Bluetooth
///     serial thermal printers pair with the phone like any Bluetooth
///     device, then accept the same raw ESC/POS bytes over a serial
///     profile (SPP). This wraps a third-party package
///     (`blue_thermal_printer` in the dependency snippet) because Flutter
///     has no built-in classic-Bluetooth API. **This is the one part of
///     this whole codebase I have the least confidence in without being
///     able to run it**: Bluetooth plugin APIs change between versions
///     more than a stable TCP socket ever would, and I can't verify the
///     exact method names/signatures against the current version on
///     pub.dev from inside this sandbox. Treat the class names, method
///     signatures, and even the package choice itself as a starting
///     point to verify against the package's current documentation
///     before relying on it, not as confirmed-working code.
abstract class ThermalPrinterConnection {
  Future<void> connect();
  Future<void> write(Uint8List bytes);
  Future<void> disconnect();
}

class NetworkThermalPrinterConnection implements ThermalPrinterConnection {
  final String host;
  final int port;
  Socket? _socket;

  NetworkThermalPrinterConnection({required this.host, this.port = 9100});

  @override
  Future<void> connect() async {
    _socket = await Socket.connect(host, port, timeout: const Duration(seconds: 5));
  }

  @override
  Future<void> write(Uint8List bytes) async {
    if (_socket == null) {
      throw StateError('Not connected. Call connect() first.');
    }
    _socket!.add(bytes);
    await _socket!.flush();
  }

  @override
  Future<void> disconnect() async {
    await _socket?.flush();
    await _socket?.close();
    _socket = null;
  }
}

/// See the class-level caveat above — this wraps `blue_thermal_printer`
/// (https://pub.dev/packages/blue_thermal_printer as of training data),
/// a long-standing package for classic Bluetooth (SPP) thermal printers
/// on Android. Its API is intentionally kept behind this same
/// [ThermalPrinterConnection] interface so a real integration only needs
/// to fix up the three methods below against whatever the package's
/// current API actually is, without touching anything else in this
/// feature (the ESC/POS byte generation, the settings screen, the
/// "mark as printed" flow) — all of that is transport-independent.
///
/// NOTE: this class is left UNIMPLEMENTED (throws
/// `UnimplementedError`) rather than guessed at, specifically so it
/// fails loudly and obviously instead of silently doing the wrong thing
/// if someone wires it up without first checking it against the real
/// package. Filling in the three method bodies against
/// `blue_thermal_printer`'s actual current API is the concrete next step
/// for whoever picks this up in a real Flutter + Bluetooth-hardware
/// environment.
class BluetoothThermalPrinterConnection implements ThermalPrinterConnection {
  final String deviceAddress;

  BluetoothThermalPrinterConnection({required this.deviceAddress});

  @override
  Future<void> connect() async {
    throw UnimplementedError(
      'Wire this up against blue_thermal_printer (or whichever Bluetooth '
      'printer package is current) — see the class doc comment. Needs a '
      'real paired device and real hardware to verify against, which this '
      'environment does not have.',
    );
  }

  @override
  Future<void> write(Uint8List bytes) async {
    throw UnimplementedError('See connect().');
  }

  @override
  Future<void> disconnect() async {
    throw UnimplementedError('See connect().');
  }
}
