import 'package:flutter/material.dart';

import '../data/printer_preferences_local_db.dart';

/// Lets a collector set up the printer their device will use. Network
/// printers (enter an IP address) work end-to-end today. Bluetooth
/// printer selection is included in this screen's flow because it's
/// part of the same user-facing feature, but actually connecting to one
/// depends on `BluetoothThermalPrinterConnection`, which is currently
/// unimplemented — see that class's doc comment for why, and what
/// finishing it actually requires (real hardware to verify against).
class PrinterSettingsScreen extends StatefulWidget {
  final PrinterPreferencesLocalDb preferencesDb;

  const PrinterSettingsScreen({super.key, required this.preferencesDb});

  @override
  State<PrinterSettingsScreen> createState() => _PrinterSettingsScreenState();
}

class _PrinterSettingsScreenState extends State<PrinterSettingsScreen> {
  PrinterPreference? _current;
  final _hostController = TextEditingController();
  final _portController = TextEditingController(text: '9100');
  final _labelController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final pref = await widget.preferencesDb.get();
    if (!mounted) return;
    setState(() => _current = pref);
    if (pref != null && pref.kind == PrinterKind.network) {
      final parts = pref.address.split(':');
      _hostController.text = parts.first;
      _portController.text = parts.length > 1 ? parts[1] : '9100';
      _labelController.text = pref.label;
    }
  }

  Future<void> _saveNetworkPrinter() async {
    if (_hostController.text.trim().isEmpty) return;
    final port = int.tryParse(_portController.text.trim()) ?? 9100;
    await widget.preferencesDb.save(PrinterPreference(
      kind: PrinterKind.network,
      address: '${_hostController.text.trim()}:$port',
      label: _labelController.text.trim().isEmpty ? 'Network printer' : _labelController.text.trim(),
    ));
    _load();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Printer saved.')));
  }

  Future<void> _clear() async {
    await widget.preferencesDb.clear();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Printer settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (_current != null) ...[
            Card(
              child: ListTile(
                leading: Icon(_current!.kind == PrinterKind.network ? Icons.wifi : Icons.bluetooth),
                title: Text(_current!.label),
                subtitle: Text(_current!.address),
                trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: _clear),
              ),
            ),
            const SizedBox(height: 16),
          ],
          const Text('WiFi / network printer', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          const Text(
            'Most WiFi thermal printers accept receipts on port 9100 by default. '
            'Check the printer\'s own settings menu for its IP address.',
            style: TextStyle(fontSize: 12, color: Colors.grey),
          ),
          const SizedBox(height: 12),
          TextField(controller: _labelController, decoration: const InputDecoration(labelText: 'Name (e.g. "Front desk printer")')),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              flex: 3,
              child: TextField(controller: _hostController, decoration: const InputDecoration(labelText: 'IP address')),
            ),
            const SizedBox(width: 8),
            Expanded(
              flex: 1,
              child: TextField(
                controller: _portController,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Port'),
              ),
            ),
          ]),
          const SizedBox(height: 12),
          FilledButton(onPressed: _saveNetworkPrinter, child: const Text('Save network printer')),
          const Divider(height: 32),
          const Text('Bluetooth printer', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          const Text(
            'Bluetooth printer pairing isn\'t finished in this build yet — it needs '
            'real hardware to verify against. Use a WiFi printer for now, or see '
            'BluetoothThermalPrinterConnection\'s notes for what\'s left to wire up.',
            style: TextStyle(fontSize: 12, color: Colors.grey),
          ),
        ],
      ),
    );
  }
}
