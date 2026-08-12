import 'package:flutter/material.dart';

import '../data/funerals_repository.dart';
import '../domain/funeral_event.dart';
import 'funeral_detail_screen.dart';

class FuneralListScreen extends StatefulWidget {
  final FuneralsRepository repository;

  /// Passed straight through to FuneralDetailScreen — see the note there
  /// on why these are builder callbacks rather than direct imports.
  final Widget Function(BuildContext context, FuneralEvent funeral)? buildGiftLedgerScreen;
  final Widget Function(BuildContext context, FuneralEvent funeral)? buildExpenseScreen;
  final Widget Function(BuildContext context, FuneralEvent funeral)? buildAttendanceScreen;
  final Widget Function(BuildContext context, String paymentId)? buildReceiptScreen;

  const FuneralListScreen({
    super.key,
    required this.repository,
    this.buildGiftLedgerScreen,
    this.buildExpenseScreen,
    this.buildAttendanceScreen,
    this.buildReceiptScreen,
  });

  @override
  State<FuneralListScreen> createState() => _FuneralListScreenState();
}

class _FuneralListScreenState extends State<FuneralListScreen> {
  List<FuneralEvent> _funerals = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load(forceRefresh: true);
  }

  Future<void> _load({bool forceRefresh = false}) async {
    setState(() => _loading = true);
    final funerals = await widget.repository.getFunerals(forceRefresh: forceRefresh);
    if (!mounted) return;
    setState(() {
      _funerals = funerals;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Funerals')),
      body: RefreshIndicator(
        onRefresh: () => _load(forceRefresh: true),
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _funerals.isEmpty
                ? ListView(children: const [
                    Padding(
                      padding: EdgeInsets.all(32),
                      child: Center(child: Text('No funerals are currently collecting.')),
                    ),
                  ])
                : ListView.separated(
                    itemCount: _funerals.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, i) {
                      final f = _funerals[i];
                      return ListTile(
                        title: Row(children: [
                          Flexible(child: Text(f.deceasedName, style: const TextStyle(fontWeight: FontWeight.w600))),
                          if (f.pendingSync) ...[
                            const SizedBox(width: 8),
                            const Icon(Icons.sync, size: 14, color: Colors.orange),
                          ],
                        ]),
                        subtitle: Text(
                          '${f.deceasedFamilyName} family · own-family rate GH₵${f.ownFamilyAmount}'
                          '${f.pendingSync ? ' · waiting to sync' : ''}',
                        ),
                        onTap: () => Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (_) => FuneralDetailScreen(
                              repository: widget.repository,
                              funeral: f,
                              buildGiftLedgerScreen: widget.buildGiftLedgerScreen == null
                                  ? null
                                  : (ctx) => widget.buildGiftLedgerScreen!(ctx, f),
                              buildExpenseScreen: widget.buildExpenseScreen == null
                                  ? null
                                  : (ctx) => widget.buildExpenseScreen!(ctx, f),
                              buildAttendanceScreen: widget.buildAttendanceScreen == null
                                  ? null
                                  : (ctx) => widget.buildAttendanceScreen!(ctx, f),
                              buildReceiptScreen: widget.buildReceiptScreen,
                            ),
                          ),
                        ).then((_) => _load()),
                      );
                    },
                  ),
      ),
    );
  }
}
