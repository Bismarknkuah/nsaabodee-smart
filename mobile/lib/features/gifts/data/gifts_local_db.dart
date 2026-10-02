import 'dart:convert';

import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

import '../domain/gift_donation.dart';

/// A completely separate SQLite database file from
/// funerals/data/funerals_local_db.dart — not just a separate table.
/// The master brief's "never mix both ledgers" rule is enforced here the
/// same way it is on the backend: there is no shared code path, no shared
/// table, and no join between gift donations and contribution obligations
/// anywhere in this app.
class GiftsLocalDb {
  static const _dbName = 'nsaabodee_gifts.db';
  static const _dbVersion = 1;

  Database? _db;

  Future<Database> get _database async {
    if (_db != null) return _db!;
    final path = join(await getDatabasesPath(), _dbName);
    _db = await openDatabase(
      path,
      version: _dbVersion,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE gift_donations (
            id TEXT PRIMARY KEY,
            funeral_event_id TEXT NOT NULL,
            donor_name TEXT NOT NULL,
            donor_phone TEXT,
            amount_cash TEXT NOT NULL,
            gift_item TEXT,
            estimated_item_value TEXT,
            receipt_number TEXT NOT NULL,
            pending_sync INTEGER NOT NULL DEFAULT 0
          )
        ''');
        await db.execute('''
          CREATE TABLE gift_sync_queue (
            op_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            queued_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
          )
        ''');
        await db.execute('''
          CREATE TABLE gift_sync_results (
            local_id TEXT PRIMARY KEY,
            confirmed_id TEXT NOT NULL
          )
        ''');
        await db.execute('CREATE INDEX idx_gifts_funeral ON gift_donations(funeral_event_id)');
      },
    );
    return _db!;
  }

  Future<List<GiftDonation>> listForFuneral(String funeralId) async {
    final db = await _database;
    final rows = await db.query('gift_donations', where: 'funeral_event_id = ?', whereArgs: [funeralId], orderBy: 'rowid DESC');
    return rows.map(GiftDonation.fromSqlite).toList();
  }

  Future<void> upsert(GiftDonation donation) async {
    final db = await _database;
    await db.insert('gift_donations', donation.toSqlite(), conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertMany(List<GiftDonation> donations) async {
    final db = await _database;
    final batch = db.batch();
    for (final d in donations) {
      batch.insert('gift_donations', d.toSqlite(), conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  Future<void> deleteLocal(String id) async {
    final db = await _database;
    await db.delete('gift_donations', where: 'id = ?', whereArgs: [id]);
  }

  Future<void> enqueue(String opId, Map<String, dynamic> payload) async {
    final db = await _database;
    await db.insert('gift_sync_queue', {
      'op_id': opId,
      'payload': _encode(payload),
      'queued_at': DateTime.now().toIso8601String(),
      'attempts': 0,
    });
  }

  Future<List<Map<String, dynamic>>> pendingOps() async {
    final db = await _database;
    final rows = await db.query('gift_sync_queue', orderBy: 'queued_at ASC');
    return rows.map((r) => {'op_id': r['op_id'], 'payload': _decode(r['payload'] as String)}).toList();
  }

  Future<void> markOpFailed(String opId, String error) async {
    final db = await _database;
    await db.rawUpdate('UPDATE gift_sync_queue SET attempts = attempts + 1, last_error = ? WHERE op_id = ?', [error, opId]);
  }

  Future<void> removeOp(String opId) async {
    final db = await _database;
    await db.delete('gift_sync_queue', where: 'op_id = ?', whereArgs: [opId]);
  }

  Future<void> setSyncResult(String localId, String confirmedId) async {
    final db = await _database;
    await db.insert('gift_sync_results', {'local_id': localId, 'confirmed_id': confirmedId},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<String?> getSyncResult(String localId) async {
    final db = await _database;
    final rows = await db.query('gift_sync_results', where: 'local_id = ?', whereArgs: [localId]);
    if (rows.isEmpty) return null;
    return rows.first['confirmed_id'] as String;
  }

  String _encode(Map<String, dynamic> payload) => jsonEncode(payload);

  Map<String, dynamic> _decode(String raw) => jsonDecode(raw) as Map<String, dynamic>;
}
