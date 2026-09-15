import 'package:flutter/material.dart';

import '../data/funeral_logistics_repository.dart';
import '../domain/funeral_logistics_models.dart';

class AttendanceScreen extends StatefulWidget {
  final FuneralLogisticsRepository repository;
  final String funeralId;
  final String funeralTitle;
  // Optional live member search, wired by the app's composition root so
  // this feature doesn't need to import the members feature directly.
  final Future<List<({String id, String name})>> Function(String query)? searchMembers;

  const AttendanceScreen({
    super.key,
    required this.repository,
    required this.funeralId,
    required this.funeralTitle,
    this.searchMembers,
  });

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  List<FuneralAttendanceRecord> _records = [];
  bool _loading = true;
  final _guestController = TextEditingController();
  final _memberQueryController = TextEditingController();
  List<({String id, String name})> _memberResults = [];

  @override
  void initState() {
    super.initState();
    _load(forceRefresh: true);
  }

  Future<void> _load({bool forceRefresh = false}) async {
    setState(() => _loading = true);
    final records = await widget.repository.getAttendance(widget.funeralId, forceRefresh: forceRefresh);
    if (!mounted) return;
    setState(() {
      _records = records;
      _loading = false;
    });
  }

  Future<void> _searchMembers(String query) async {
    if (widget.searchMembers == null || query.trim().length < 2) {
      setState(() => _memberResults = []);
      return;
    }
    final results = await widget.searchMembers!(query);
    if (!mounted) return;
    setState(() => _memberResults = results);
  }

  Future<void> _checkInMember(String id, String name) async {
    await widget.repository.recordAttendance(funeralId: widget.funeralId, memberId: id, memberName: name);
    _memberQueryController.clear();
    setState(() => _memberResults = []);
    _load();
  }

  Future<void> _addGuest() async {
    final name = _guestController.text.trim();
    if (name.isEmpty) return;
    await widget.repository.recordAttendance(funeralId: widget.funeralId, guestName: name);
    _guestController.clear();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Attendance — ${widget.funeralTitle}')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              children: [
                if (widget.searchMembers != null) ...[
                  TextField(
                    controller: _memberQueryController,
                    decoration: const InputDecoration(labelText: 'Check in a member', prefixIcon: Icon(Icons.search)),
                    onChanged: _searchMembers,
                  ),
                  if (_memberResults.isNotEmpty)
                    SizedBox(
                      height: 120,
                      child: ListView(
                        children: _memberResults
                            .map((m) => ListTile(title: Text(m.name), onTap: () => _checkInMember(m.id, m.name)))
                            .toList(),
                      ),
                    ),
                  const SizedBox(height: 8),
                ],
                Row(children: [
                  Expanded(
                    child: TextField(
                      controller: _guestController,
                      decoration: const InputDecoration(labelText: 'Log a guest by name'),
                    ),
                  ),
                  IconButton(icon: const Icon(Icons.add_circle), onPressed: _addGuest),
                ]),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => _load(forceRefresh: true),
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : ListView.separated(
                      itemCount: _records.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, i) {
                        final r = _records[i];
                        return ListTile(
                          leading: Icon(r.memberId != null ? Icons.badge : Icons.person_outline),
                          title: Row(children: [
                            Flexible(child: Text(r.displayName)),
                            if (r.pendingSync) ...[
                              const SizedBox(width: 8),
                              const Icon(Icons.sync, size: 14, color: Colors.orange),
                            ],
                          ]),
                          subtitle: Text(r.memberId != null ? 'Member' : 'Guest'),
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
