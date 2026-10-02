import 'package:flutter/material.dart';

import '../data/gifts_repository.dart';
import '../domain/gift_donation.dart';

/// Deliberately a separate screen (not a tab bolted onto
/// FuneralDetailScreen's existing ListView) reached via its own button,
/// using its own purple accent color — the same "never let these two
/// ledgers visually blur together" choice made on the web frontend.
class GiftLedgerScreen extends StatefulWidget {
  final GiftsRepository repository;
  final String funeralId;
  final String funeralTitle;

  /// Builds a receipt-viewing screen for a given gift donation id — an
  /// injected callback for the same decoupling reason as
  /// FuneralDetailScreen's builder callbacks.
  final Widget Function(BuildContext context, String donationId)? buildReceiptScreen;

  const GiftLedgerScreen({
    super.key,
    required this.repository,
    required this.funeralId,
    required this.funeralTitle,
    this.buildReceiptScreen,
  });

  @override
  State<GiftLedgerScreen> createState() => _GiftLedgerScreenState();
}

class _GiftLedgerScreenState extends State<GiftLedgerScreen> {
  static const _violet = Color(0xFF7A4B8C);

  List<GiftDonation> _donations = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load(forceRefresh: true);
  }

  Future<void> _load({bool forceRefresh = false}) async {
    setState(() => _loading = true);
    final donations = await widget.repository.getDonations(widget.funeralId, forceRefresh: forceRefresh);
    if (!mounted) return;
    setState(() {
      _donations = donations;
      _loading = false;
    });
  }

  Future<void> _showRecordSheet() async {
    final nameController = TextEditingController();
    final phoneController = TextEditingController();
    final cashController = TextEditingController();
    final itemController = TextEditingController();
    final valueController = TextEditingController();

    final submitted = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (context) => Padding(
        padding: EdgeInsets.only(left: 16, right: 16, top: 16, bottom: MediaQuery.of(context).viewInsets.bottom + 16),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Record a gift donation (Ledger 2)',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: _violet)),
              const SizedBox(height: 4),
              const Text('The donor doesn\'t need to be a registered member.', style: TextStyle(fontSize: 12, color: Colors.grey)),
              const SizedBox(height: 12),
              TextField(controller: nameController, decoration: const InputDecoration(labelText: "Donor's name")),
              TextField(controller: phoneController, decoration: const InputDecoration(labelText: "Donor's phone (optional)")),
              const SizedBox(height: 8),
              TextField(controller: cashController, keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Cash amount (optional)')),
              TextField(controller: itemController, decoration: const InputDecoration(labelText: 'Gift item (optional)')),
              TextField(controller: valueController, keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Estimated item value')),
              const SizedBox(height: 16),
              FilledButton(
                style: FilledButton.styleFrom(backgroundColor: _violet),
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Record & issue receipt'),
              ),
            ],
          ),
        ),
      ),
    );

    if (submitted == true && nameController.text.trim().isNotEmpty) {
      final donationId = await widget.repository.recordDonation(
        funeralId: widget.funeralId,
        donorName: nameController.text.trim(),
        donorPhone: phoneController.text.trim(),
        amountCash: cashController.text.trim().isEmpty ? '0' : cashController.text.trim(),
        giftItem: itemController.text.trim(),
        estimatedItemValue: valueController.text.trim().isEmpty ? null : valueController.text.trim(),
      );
      _load();
      if (!mounted) return;
      if (donationId != null && widget.buildReceiptScreen != null) {
        final viewReceipt = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Gift recorded'),
            content: const Text('A receipt has been issued. View it now?'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Not now')),
              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('View receipt')),
            ],
          ),
        );
        if (viewReceipt == true && mounted) {
          Navigator.push(context, MaterialPageRoute(builder: (ctx) => widget.buildReceiptScreen!(ctx, donationId)));
        }
      } else if (donationId == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Gift queued — it'll issue a receipt once this device syncs.")),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Gifts — ${widget.funeralTitle}'),
        backgroundColor: _violet,
        foregroundColor: Colors.white,
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showRecordSheet,
        backgroundColor: _violet,
        icon: const Icon(Icons.card_giftcard),
        label: const Text('Record gift'),
      ),
      body: RefreshIndicator(
        onRefresh: () => _load(forceRefresh: true),
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _donations.isEmpty
                ? ListView(children: const [
                    Padding(padding: EdgeInsets.all(32), child: Center(child: Text('No gifts recorded yet.'))),
                  ])
                : ListView.separated(
                    itemCount: _donations.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, i) {
                      final d = _donations[i];
                      return ListTile(
                        leading: Icon(Icons.card_giftcard, color: _violet.withOpacity(0.7)),
                        title: Row(children: [
                          Flexible(child: Text(d.donorName, style: const TextStyle(fontWeight: FontWeight.w600))),
                          if (d.pendingSync) ...[
                            const SizedBox(width: 8),
                            const Icon(Icons.sync, size: 14, color: Colors.orange),
                          ],
                        ]),
                        subtitle: Text(
                          [
                            if (d.amountCash != '0' && d.amountCash != '0.00') 'GH₵${d.amountCash}',
                            if (d.giftItem.isNotEmpty) d.giftItem,
                          ].join(' + '),
                        ),
                        trailing: Text('GH₵${d.totalValue.toStringAsFixed(2)}',
                            style: const TextStyle(fontWeight: FontWeight.w600)),
                      );
                    },
                  ),
      ),
    );
  }
}
