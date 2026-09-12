import 'package:flutter/material.dart';

import '../data/funerals_repository.dart';
import '../domain/funeral_event.dart';

class FuneralDetailScreen extends StatefulWidget {
  final FuneralsRepository repository;
  final FuneralEvent funeral;

  /// Provided by the app's composition root (not imported directly here,
  /// to keep the funerals, gifts, and funeral_logistics features
  /// decoupled) — builds the separate Gift Ledger screen (Ledger 2) for
  /// this funeral.
  final Widget Function(BuildContext context)? buildGiftLedgerScreen;
  final Widget Function(BuildContext context)? buildExpenseScreen;
  final Widget Function(BuildContext context)? buildAttendanceScreen;

  /// Builds a receipt-viewing screen for a given contribution payment id
  /// — kept as an injected callback for the same decoupling reason as
  /// the other builders above.
  final Widget Function(BuildContext context, String paymentId)? buildReceiptScreen;

  const FuneralDetailScreen({
    super.key,
    required this.repository,
    required this.funeral,
    this.buildGiftLedgerScreen,
    this.buildExpenseScreen,
    this.buildAttendanceScreen,
    this.buildReceiptScreen,
  });

  @override
  State<FuneralDetailScreen> createState() => _FuneralDetailScreenState();
}

class _FuneralDetailScreenState extends State<FuneralDetailScreen> {
  List<ContributionObligation> _obligations = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load(forceRefresh: true);
  }

  Future<void> _load({bool forceRefresh = false}) async {
    setState(() => _loading = true);
    final obligations = await widget.repository.getObligations(widget.funeral.id, forceRefresh: forceRefresh);
    if (!mounted) return;
    setState(() {
      _obligations = obligations;
      _loading = false;
    });
  }

  Future<void> _recordPayment(ContributionObligation obligation) async {
    final controller = TextEditingController(text: obligation.balance.toStringAsFixed(2));
    String method = 'cash';

    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.only(
            left: 16, right: 16, top: 16,
            bottom: MediaQuery.of(context).viewInsets.bottom + 16,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('${obligation.memberName} owes GH₵${obligation.balance.toStringAsFixed(2)}',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              TextField(
                controller: controller,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Amount'),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: method,
                items: const [
                  DropdownMenuItem(value: 'cash', child: Text('Cash')),
                  DropdownMenuItem(value: 'mobile_money', child: Text('Mobile Money')),
                  DropdownMenuItem(value: 'bank', child: Text('Bank')),
                  DropdownMenuItem(value: 'other', child: Text('Other')),
                ],
                onChanged: (v) => setSheetState(() => method = v ?? 'cash'),
                decoration: const InputDecoration(labelText: 'Payment method'),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Record & issue receipt'),
              ),
            ],
          ),
        ),
      ),
    );

    if (confirmed == true) {
      final result = await widget.repository.recordPayment(
        funeral: widget.funeral,
        obligation: obligation,
        amount: controller.text.trim(),
        method: method,
      );
      if (!mounted) return;
      if (result.error != null) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(result.error!)));
        return;
      }
      _load();
      if (result.paymentId != null && widget.buildReceiptScreen != null) {
        final viewReceipt = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Payment recorded'),
            content: const Text('A receipt has been issued. View it now?'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Not now')),
              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('View receipt')),
            ],
          ),
        );
        if (viewReceipt == true && mounted) {
          Navigator.push(context, MaterialPageRoute(builder: (ctx) => widget.buildReceiptScreen!(ctx, result.paymentId!)));
        }
      } else if (result.paymentId == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Payment queued — it'll issue a receipt once this device syncs.")),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.funeral.deceasedName),
        actions: [
          if (widget.buildExpenseScreen != null)
            IconButton(
              icon: const Icon(Icons.receipt_long),
              tooltip: 'Expenses',
              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: widget.buildExpenseScreen!)),
            ),
          if (widget.buildAttendanceScreen != null)
            IconButton(
              icon: const Icon(Icons.how_to_reg),
              tooltip: 'Attendance',
              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: widget.buildAttendanceScreen!)),
            ),
          if (widget.buildGiftLedgerScreen != null)
            IconButton(
              icon: const Icon(Icons.card_giftcard),
              tooltip: 'Gift donations (Ledger 2)',
              onPressed: () => Navigator.push(
                context,
                MaterialPageRoute(builder: widget.buildGiftLedgerScreen!),
              ),
            ),
        ],
      ),
      body: Column(
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            color: Theme.of(context).colorScheme.surfaceVariant,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${widget.funeral.deceasedFamilyName} family rate: GH₵${widget.funeral.ownFamilyAmount}'),
                Text('General rate: GH₵${widget.funeral.generalMaleAmount} (male) / '
                    'GH₵${widget.funeral.generalFemaleAmount} (female)'),
                if (widget.funeral.pendingSync)
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Text(
                      "This funeral hasn't synced yet — its ledger will appear once connected.",
                      style: TextStyle(color: Colors.orange),
                    ),
                  ),
              ],
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => _load(forceRefresh: true),
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _obligations.isEmpty
                      ? ListView(children: const [
                          Padding(padding: EdgeInsets.all(32), child: Center(child: Text('No ledger yet.'))),
                        ])
                      : ListView.separated(
                          itemCount: _obligations.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, i) {
                            final o = _obligations[i];
                            final statusColor = {
                              'paid': Colors.green,
                              'partial': Colors.orange,
                              'unpaid': Colors.red,
                            }[o.paymentStatus]!;
                            return ListTile(
                              title: Text(o.memberName),
                              subtitle: Text(
                                '${o.rateType == RateType.ownFamily ? "Own family" : "General"} · '
                                'owes GH₵${o.expectedAmount}, paid GH₵${o.amountPaid}',
                              ),
                              trailing: o.paymentStatus == 'paid'
                                  ? Icon(Icons.check_circle, color: statusColor)
                                  : TextButton(
                                      onPressed: () => _recordPayment(o),
                                      child: const Text('Record payment'),
                                    ),
                            );
                          },
                        ),
            ),
          ),
        ],
      ),
    );
  }
}
