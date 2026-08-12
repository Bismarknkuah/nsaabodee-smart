import 'dart:convert';
import 'dart:typed_data';

/// Builds raw ESC/POS byte sequences for a thermal receipt printer.
///
/// This is deliberately hand-written against the ESC/POS command set
/// directly rather than wrapping a third-party "receipt builder" package
/// — the protocol itself (developed by Epson, adopted as the de facto
/// standard by nearly every thermal receipt printer manufacturer since)
/// has been stable for decades, so there's very little risk in encoding
/// it directly, versus depending on a package whose API might have
/// drifted since this was written. The actual TRANSPORT (Bluetooth or
/// network socket) is a separate concern — see
/// `thermal_printer_connection.dart` — this class only produces bytes.
class EscPosBuilder {
  final List<int> _bytes = [];

  static const _esc = 0x1B;
  static const _gs = 0x1D;

  EscPosBuilder() {
    // ESC @ — initialize printer (clear buffer, reset formatting).
    _bytes.addAll([_esc, 0x40]);
  }

  EscPosBuilder text(String value) {
    _bytes.addAll(_encodeText(value));
    return this;
  }

  EscPosBuilder line(String value) {
    text(value);
    newline();
    return this;
  }

  EscPosBuilder newline([int count = 1]) {
    for (var i = 0; i < count; i++) {
      _bytes.add(0x0A);
    }
    return this;
  }

  EscPosBuilder centerAlign() {
    // ESC a 1 — align center.
    _bytes.addAll([_esc, 0x61, 0x01]);
    return this;
  }

  EscPosBuilder leftAlign() {
    // ESC a 0 — align left.
    _bytes.addAll([_esc, 0x61, 0x00]);
    return this;
  }

  EscPosBuilder bold(bool on) {
    // ESC E n — bold on/off.
    _bytes.addAll([_esc, 0x45, on ? 0x01 : 0x00]);
    return this;
  }

  EscPosBuilder doubleHeight(bool on) {
    // GS ! n — character size. 0x11 = double width + double height.
    _bytes.addAll([_gs, 0x21, on ? 0x11 : 0x00]);
    return this;
  }

  EscPosBuilder divider([int width = 32]) {
    line(List.filled(width, "-").join());
    return this;
  }

  /// A left-label / right-value line, the way every field on a receipt
  /// (e.g. "Receipt No.   BODI-000123") should be laid out — right-pads
  /// the label so the value lands flush against the right margin on a
  /// standard 32-column thermal roll.
  EscPosBuilder labelValue(String label, String value, {int width = 32}) {
    final space = width - label.length - value.length;
    final padded = space > 0 ? label + List.filled(space, " ").join() + value : "$label $value";
    line(padded);
    return this;
  }

  EscPosBuilder cutPaper() {
    // GS V 1 — partial cut. Most thermal printers support this; a
    // full cut (GS V 0) is used instead by some models. Both are common
    // enough that a real deployment should verify against the specific
    // printer model in use.
    _bytes.addAll([_gs, 0x56, 0x01]);
    return this;
  }

  EscPosBuilder feedAndCut([int feedLines = 3]) {
    newline(feedLines);
    cutPaper();
    return this;
  }

  Uint8List build() => Uint8List.fromList(_bytes);

  List<int> _encodeText(String value) {
    // Most thermal printers default to a single-byte code page (commonly
    // CP437 or similar) rather than full UTF-8. Non-ASCII characters
    // (e.g. "ɛ" in "Nsaabodeɛ", or "₵" for cedis) are NOT guaranteed to
    // print correctly on every printer without selecting the matching
    // code page first (ESC t n) — that selection is printer-model
    // specific, so it's deliberately left to the caller to configure for
    // their exact hardware rather than guessed at here. ASCII text always
    // prints correctly regardless of code page.
    return latin1.encode(value.replaceAll(RegExp(r'[^\x00-\xFF]'), '?'));
  }
}
