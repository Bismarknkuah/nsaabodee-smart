import 'package:flutter/material.dart';

import '../data/families_repository.dart';
import '../domain/family.dart';

class FamilyRegistryScreen extends StatefulWidget {
  final FamiliesRepository repository;

  const FamilyRegistryScreen({super.key, required this.repository});

  @override
  State<FamilyRegistryScreen> createState() => _FamilyRegistryScreenState();
}

class _FamilyRegistryScreenState extends State<FamilyRegistryScreen> {
  List<Family> _families = [];
  bool _loading = true;
  bool _includeInactive = false;

  @override
  void initState() {
    super.initState();
    _load(forceRefresh: true);
  }

  Future<void> _load({bool forceRefresh = false}) async {
    setState(() => _loading = true);
    final families = await widget.repository.getFamilies(
      includeInactive: _includeInactive,
      forceRefresh: forceRefresh,
    );
    if (!mounted) return;
    setState(() {
      _families = families;
      _loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Family Registry'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Add family',
            onPressed: _showAddFamilySheet,
          ),
        ],
      ),
      body: Column(
        children: [
          SwitchListTile(
            title: const Text('Show deactivated, merged & deleted'),
            value: _includeInactive,
            onChanged: (v) {
              setState(() => _includeInactive = v);
              _load();
            },
          ),
          const Divider(height: 1),
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => _load(forceRefresh: true),
              child: _loading
                  ? const Center(child: CircularProgressIndicator())
                  : _families.isEmpty
                      ? ListView(
                          children: const [
                            Padding(
                              padding: EdgeInsets.all(32),
                              child: Center(child: Text('No families yet. Tap + to add one.')),
                            ),
                          ],
                        )
                      : ListView.separated(
                          itemCount: _families.length,
                          separatorBuilder: (_, __) => const Divider(height: 1),
                          itemBuilder: (context, i) => _FamilyTile(
                            family: _families[i],
                            onAction: (action) => _handleAction(action, _families[i]),
                          ),
                        ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _handleAction(_FamilyAction action, Family family) async {
    switch (action) {
      case _FamilyAction.rename:
        await _showRenameSheet(family);
        break;
      case _FamilyAction.deactivate:
        await widget.repository.deactivateFamily(family);
        _load();
        break;
      case _FamilyAction.reactivate:
        await widget.repository.reactivateFamily(family);
        _load();
        break;
      case _FamilyAction.delete:
        final confirmed = await _confirmDelete(family);
        if (confirmed == true) {
          await widget.repository.deleteFamily(family);
          _load();
        }
        break;
      case _FamilyAction.merge:
        await _showMergeSheet(family);
        break;
    }
  }

  Future<void> _showAddFamilySheet() async {
    final controller = TextEditingController();
    final name = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (context) => Padding(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Add family', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Family name', hintText: 'e.g. Asona'),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => Navigator.pop(context, controller.text.trim()),
              child: const Text('Add family'),
            ),
          ],
        ),
      ),
    );
    if (name != null && name.isNotEmpty) {
      await widget.repository.addFamily(name: name);
      _load();
    }
  }

  Future<void> _showRenameSheet(Family family) async {
    final controller = TextEditingController(text: family.name);
    final name = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (context) => Padding(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: MediaQuery.of(context).viewInsets.bottom + 16,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Rename "${family.name}"', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            TextField(controller: controller, autofocus: true),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => Navigator.pop(context, controller.text.trim()),
              child: const Text('Save name'),
            ),
          ],
        ),
      ),
    );
    if (name != null && name.isNotEmpty && name != family.name) {
      await widget.repository.renameFamily(family, name);
      _load();
    }
  }

  Future<void> _showMergeSheet(Family source) async {
    final candidates = _families
        .where((f) => f.id != source.id && f.status == FamilyStatus.active)
        .toList();
    final target = await showModalBottomSheet<Family>(
      context: context,
      builder: (context) => ListView(
        shrinkWrap: true,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Text(
              'Merge "${source.name}" into…',
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ),
          ...candidates.map(
            (f) => ListTile(
              title: Text(f.name),
              subtitle: Text('${f.memberCount} members'),
              onTap: () => Navigator.pop(context, f),
            ),
          ),
        ],
      ),
    );
    if (target != null) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Confirm merge'),
          content: Text(
            'All ${source.memberCount} member(s) of "${source.name}" will move to '
            '"${target.name}". This cannot be automatically undone. Continue?',
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Merge')),
          ],
        ),
      );
      if (confirmed == true) {
        await widget.repository.mergeFamilies(source: source, target: target);
        _load();
      }
    }
  }

  Future<bool?> _confirmDelete(Family family) {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Delete "${family.name}"?'),
        content: family.memberCount > 0
            ? Text(
                'This family still has ${family.memberCount} active member(s). '
                'Transfer or merge them out first.',
              )
            : const Text('This soft-deletes the family. History is kept.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          if (family.memberCount == 0)
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: Colors.red.shade700),
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Delete'),
            ),
        ],
      ),
    );
  }
}

enum _FamilyAction { rename, merge, deactivate, reactivate, delete }

class _FamilyTile extends StatelessWidget {
  final Family family;
  final void Function(_FamilyAction) onAction;

  const _FamilyTile({required this.family, required this.onAction});

  @override
  Widget build(BuildContext context) {
    final isActive = family.status == FamilyStatus.active;
    return ListTile(
      title: Row(
        children: [
          Flexible(child: Text(family.name, style: const TextStyle(fontWeight: FontWeight.w600))),
          if (family.pendingSync) ...[
            const SizedBox(width: 8),
            const Icon(Icons.sync, size: 14, color: Colors.orange),
          ],
        ],
      ),
      subtitle: Text(
        '${family.memberCount} active member${family.memberCount == 1 ? '' : 's'}'
        '${family.familyHeadName != null ? ' · Head: ${family.familyHeadName}' : ''}'
        ' · ${family.status.name}',
      ),
      trailing: PopupMenuButton<_FamilyAction>(
        onSelected: onAction,
        itemBuilder: (context) => [
          if (isActive) const PopupMenuItem(value: _FamilyAction.rename, child: Text('Rename')),
          if (isActive) const PopupMenuItem(value: _FamilyAction.merge, child: Text('Merge')),
          if (isActive)
            const PopupMenuItem(value: _FamilyAction.deactivate, child: Text('Deactivate')),
          if (family.status == FamilyStatus.deactivated)
            const PopupMenuItem(value: _FamilyAction.reactivate, child: Text('Reactivate')),
          if (isActive)
            const PopupMenuItem(value: _FamilyAction.delete, child: Text('Delete')),
        ],
      ),
    );
  }
}
