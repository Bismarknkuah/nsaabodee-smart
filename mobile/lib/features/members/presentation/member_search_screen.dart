import 'package:flutter/material.dart';

import '../data/members_api_client.dart';
import '../data/members_repository.dart';
import '../domain/member.dart';
import 'member_card_screen.dart';
import 'member_registration_screen.dart';

class MemberSearchScreen extends StatefulWidget {
  final MembersRepository repository;
  final MembersApiClient apiClient;
  final List<({String id, String name})> families;

  const MemberSearchScreen({
    super.key,
    required this.repository,
    required this.apiClient,
    required this.families,
  });

  @override
  State<MemberSearchScreen> createState() => _MemberSearchScreenState();
}

class _MemberSearchScreenState extends State<MemberSearchScreen> {
  List<Member> _members = [];
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search({bool forceRefresh = false}) async {
    final results = await widget.repository.search(query: _searchController.text.trim(), forceRefresh: forceRefresh);
    if (!mounted) return;
    setState(() => _members = results);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Members')),
      floatingActionButton: FloatingActionButton.extended(
        icon: const Icon(Icons.person_add),
        label: const Text('Register'),
        onPressed: () async {
          final registered = await Navigator.push<bool>(
            context,
            MaterialPageRoute(
              builder: (_) => MemberRegistrationScreen(repository: widget.repository, families: widget.families),
            ),
          );
          if (registered == true) _search();
        },
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              controller: _searchController,
              decoration: const InputDecoration(
                labelText: 'Search by name or phone',
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: (_) => _search(),
              onSubmitted: (_) => _search(forceRefresh: true),
            ),
          ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => _search(forceRefresh: true),
              child: _members.isEmpty
                  ? ListView(children: const [
                      Padding(padding: EdgeInsets.all(32), child: Center(child: Text('No members found.'))),
                    ])
                  : ListView.separated(
                      itemCount: _members.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (context, i) {
                        final m = _members[i];
                        return ListTile(
                          title: Row(children: [
                            Flexible(child: Text(m.fullName)),
                            if (m.pendingSync) ...[
                              const SizedBox(width: 8),
                              const Icon(Icons.sync, size: 14, color: Colors.orange),
                            ],
                          ]),
                          subtitle: Text('${m.membershipNumber} · ${m.familyName ?? "No family"}'),
                          trailing: const Icon(Icons.qr_code),
                          onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => MemberCardScreen(apiClient: widget.apiClient, member: m)),
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
