import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'pdf_file_opener.dart';

/// Shows the same receipt data the backend would hand a thermal printer
/// (see reports/receipts.py on the backend), and can now also fetch and
/// save the same PDF the web frontend's "Download PDF" link opens (see
/// reports/pdf.py on the backend). [onPrint] sends it to a real
/// Bluetooth/network thermal printer if one's configured (see the
/// printing/ feature); [loadReceiptPdfBytes] fetches the PDF form for
/// saving/viewing. Both are injected rather than importing those
/// features directly, the same decoupling pattern used throughout this
/// app (see FuneralDetailScreen's builder callbacks).
class ReceiptViewScreen extends StatefulWidget {
  final Future<String> Function() loadReceiptText;
  final Future<void> Function()? onPrint;
  final Future<Uint8List> Function()? loadReceiptPdfBytes;
  final String pdfFilename;

  const ReceiptViewScreen({
    super.key,
    required this.loadReceiptText,
    this.onPrint,
    this.loadReceiptPdfBytes,
    this.pdfFilename = 'receipt.pdf',
  });

  @override
  State<ReceiptViewScreen> createState() => _ReceiptViewScreenState();
}

class _ReceiptViewScreenState extends State<ReceiptViewScreen> {
  String? _text;
  String? _error;
  bool _printing = false;
  bool _printedThisSession = false;
  bool _downloadingPdf = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final text = await widget.loadReceiptText();
      if (!mounted) return;
      setState(() => _text = text);
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    }
  }

  Future<void> _print() async {
    if (widget.onPrint == null) return;
    setState(() => _printing = true);
    try {
      await widget.onPrint!();
      if (!mounted) return;
      setState(() {
        _printing = false;
        _printedThisSession = true;
      });
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Receipt printed and confirmed.')));
    } catch (e) {
      if (!mounted) return;
      setState(() => _printing = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Could not print: $e')),
      );
    }
  }

  Future<void> _downloadPdf() async {
    if (widget.loadReceiptPdfBytes == null) return;
    setState(() => _downloadingPdf = true);
    try {
      final bytes = await widget.loadReceiptPdfBytes!();
      // saveAndOpen throws UnimplementedError until a file-opener package
      // is wired up (see PdfFileOpener) — fall back to just saving and
      // telling the collector where it landed, rather than the screen
      // breaking outright in the meantime.
      try {
        await PdfFileOpener.saveAndOpen(bytes, widget.pdfFilename);
      } on UnimplementedError {
        final path = await PdfFileOpener.save(bytes, widget.pdfFilename);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('PDF saved to $path')));
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not download PDF: $e')));
    } finally {
      if (mounted) setState(() => _downloadingPdf = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Receipt'),
        actions: [
          if (widget.loadReceiptPdfBytes != null)
            IconButton(
              icon: _downloadingPdf
                  ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.picture_as_pdf),
              tooltip: 'Download PDF',
              onPressed: _downloadingPdf ? null : _downloadPdf,
            ),
          if (_text != null)
            IconButton(
              icon: const Icon(Icons.copy),
              tooltip: 'Copy',
              onPressed: () {
                Clipboard.setData(ClipboardData(text: _text!));
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Receipt copied')));
              },
            ),
        ],
      ),
      floatingActionButton: (widget.onPrint == null || _text == null)
          ? null
          : FloatingActionButton.extended(
              onPressed: _printing ? null : _print,
              icon: _printedThisSession ? const Icon(Icons.check) : const Icon(Icons.print),
              label: Text(_printing ? 'Printing…' : (_printedThisSession ? 'Printed again?' : 'Print receipt')),
            ),
      body: Center(
        child: _error != null
            ? Padding(padding: const EdgeInsets.all(24), child: Text(_error!, textAlign: TextAlign.center))
            : _text == null
                ? const CircularProgressIndicator()
                : Container(
                    margin: const EdgeInsets.all(24),
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(border: Border.all(color: Colors.grey.shade300), borderRadius: BorderRadius.circular(4)),
                    child: SelectableText(_text!, style: const TextStyle(fontFamily: 'monospace', fontSize: 13)),
                  ),
      ),
    );
  }
}
