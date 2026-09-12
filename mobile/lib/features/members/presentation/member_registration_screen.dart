import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../data/members_repository.dart';

class MemberRegistrationScreen extends StatefulWidget {
  final MembersRepository repository;
  final List<({String id, String name})> families;

  const MemberRegistrationScreen({super.key, required this.repository, required this.families});

  @override
  State<MemberRegistrationScreen> createState() => _MemberRegistrationScreenState();
}

class _MemberRegistrationScreenState extends State<MemberRegistrationScreen> {
  final _nameController = TextEditingController();
  final _phoneController = TextEditingController();
  final _ghanaCardController = TextEditingController();
  String _gender = 'male';
  String? _familyId;
  String? _photoPath;
  bool _saving = false;

  Future<void> _pickPhoto() async {
    final picker = ImagePicker();
    final photo = await picker.pickImage(source: ImageSource.camera, maxWidth: 1024, imageQuality: 85);
    if (photo != null) setState(() => _photoPath = photo.path);
  }

  Future<void> _submit() async {
    if (_nameController.text.trim().isEmpty) return;
    setState(() => _saving = true);
    String? familyName;
    for (final f in widget.families) {
      if (f.id == _familyId) {
        familyName = f.name;
        break;
      }
    }

    await widget.repository.registerMember(
      fullName: _nameController.text.trim(),
      gender: _gender,
      familyId: _familyId,
      familyName: familyName,
      phone: _phoneController.text.trim(),
      ghanaCardNumber: _ghanaCardController.text.trim().isEmpty ? null : _ghanaCardController.text.trim(),
      photoLocalPath: _photoPath,
    );

    if (!mounted) return;
    Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Register a member')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'This works offline. A membership number and QR code are assigned '
            'the moment this syncs — the moment a connection is available.',
            style: TextStyle(color: Colors.grey, fontSize: 13),
          ),
          const SizedBox(height: 16),
          Center(
            child: GestureDetector(
              onTap: _pickPhoto,
              child: CircleAvatar(
                radius: 40,
                backgroundImage: _photoPath != null ? FileImage(File(_photoPath!)) as ImageProvider : null,
                child: _photoPath == null ? const Icon(Icons.camera_alt) : null,
              ),
            ),
          ),
          const SizedBox(height: 16),
          TextField(controller: _nameController, decoration: const InputDecoration(labelText: 'Full name')),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _gender,
            items: const [
              DropdownMenuItem(value: 'male', child: Text('Male')),
              DropdownMenuItem(value: 'female', child: Text('Female')),
            ],
            onChanged: (v) => setState(() => _gender = v ?? 'male'),
            decoration: const InputDecoration(labelText: 'Gender'),
          ),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(
            value: _familyId,
            items: widget.families
                .map((f) => DropdownMenuItem(value: f.id, child: Text(f.name)))
                .toList(),
            onChanged: (v) => setState(() => _familyId = v),
            decoration: const InputDecoration(labelText: 'Family'),
          ),
          const SizedBox(height: 8),
          TextField(controller: _phoneController, decoration: const InputDecoration(labelText: 'Phone')),
          const SizedBox(height: 8),
          TextField(controller: _ghanaCardController, decoration: const InputDecoration(labelText: 'Ghana Card (optional)')),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _saving ? null : _submit,
            child: Text(_saving ? 'Registering…' : 'Register member'),
          ),
        ],
      ),
    );
  }
}
