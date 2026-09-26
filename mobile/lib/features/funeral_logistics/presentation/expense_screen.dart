import 'package:flutter/material.dart';

import '../data/funeral_logistics_repository.dart';
import '../domain/funeral_logistics_models.dart';

class ExpenseScreen extends StatefulWidget {
  final FuneralLogisticsRepository repository;
  final String funeralId;
  final String funeralTitle;

  const ExpenseScreen({super.key, required this.repository, required this.funeralId, required this.funeralTitle});

  @override
  State<ExpenseScreen> createState() => _ExpenseScreenState();
}

class _ExpenseScreenState extends State<ExpenseScreen> {
  static const _categories = {
    'catering': 'Catering',
    'transport': 'Transport',
    'coffin': 'Coffin',
    'venue': 'Venue / Canopy / Chairs',
    'printing': 'Printing',
    'burial_fees': 'Burial Fees',
    'other': 'Other',
  };

  List<FuneralExpense> _expenses = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load(forceRefresh: true);
  }

  Future<void> _load({bool forceRefresh = false}) async {
    setState(() => _loading = true);
    final expenses = await widget.repository.getExpenses(widget.funeralId, forceRefresh: forceRefresh);
    if (!mounted) return;
    setState(() {
      _expenses = expenses;
      _loading = false;
    });
  }

  Future<void> _showRecordSheet() async {
    final descController = TextEditingController();
    final amountController = TextEditingController();
    String category = 'other';
    final today = DateTime.now();

    final submitted = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.only(left: 16, right: 16, top: 16, bottom: MediaQuery.of(context).viewInsets.bottom + 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Record expense', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              TextField(controller: descController, decoration: const InputDecoration(labelText: 'Description')),
              const SizedBox(height: 8),
              DropdownButtonFormField<String>(
                value: category,
                items: _categories.entries.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value))).toList(),
                onChanged: (v) => setSheetState(() => category = v ?? 'other'),
                decoration: const InputDecoration(labelText: 'Category'),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: amountController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Amount (GH₵)'),
              ),
              const SizedBox(height: 16),
              FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Record expense')),
            ],
          ),
        ),
      ),
    );

    if (submitted == true && descController.text.trim().isNotEmpty && amountController.text.trim().isNotEmpty) {
      await widget.repository.recordExpense(
        funeralId: widget.funeralId,
        description: descController.text.trim(),
        category: category,
        amount: amountController.text.trim(),
        paymentMethod: 'cash',
        incurredOn: today.toIso8601String().substring(0, 10),
      );
      _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    final total = _expenses.fold<double>(0, (sum, e) => sum + (double.tryParse(e.amount) ?? 0));
    return Scaffold(
      appBar: AppBar(title: Text('Expenses — ${widget.funeralTitle}')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showRecordSheet,
        icon: const Icon(Icons.receipt_long),
        label: const Text('Record expense'),
      ),
      body: Column(
        children: [
          if (_expenses.isNotEmpty)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              color: Colors.red.withOpacity(0.08),
              child: Text('Total: GH₵${total.toStringAsFixed(2)}', style: const TextStyle(fontWeight: FontWeight.bold)),
            ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => _load(forceRefresh: true),
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _expenses.isEmpty
                      ? ListView(children: const [
                          Padding(padding: EdgeInsets.all(32), child: Center(child: Text('No expenses recorded yet.'))),
                        ])
                      : ListView.separated(
                          itemCount: _expenses.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, i) {
                            final e = _expenses[i];
                            return ListTile(
                              title: Row(children: [
                                Flexible(child: Text(e.description)),
                                if (e.pendingSync) ...[
                                  const SizedBox(width: 8),
                                  const Icon(Icons.sync, size: 14, color: Colors.orange),
                                ],
                              ]),
                              subtitle: Text('${_categories[e.category] ?? e.category} · ${e.voucherNumber}'),
                              trailing: Text('−GH₵${e.amount}', style: const TextStyle(color: Colors.red)),
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
