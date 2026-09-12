import 'dart:convert';

import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

import '../domain/member.dart';

class MembersLocalDb {
  static const _dbName = 'nsaabodee_members.db';
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
          CREATE TABLE members (
            id TEXT NOT NULL,
            community_id TEXT NOT NULL,
            membership_number TEXT NOT NULL,
            full_name TEXT NOT NULL,
            gender TEXT NOT NULL,
            family_id TEXT,
            family_name TEXT,
            phone TEXT,
            status TEXT NOT NULL,
            defaulter_tier TEXT NOT NULL DEFAULT 'none',
            photo_url TEXT,
            pending_photo_local_path TEXT,
            pending_sync INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (id, community_id)
          )
        ''');
        await db.execute('''
          CREATE TABLE member_sync_queue (
            op_id TEXT PRIMARY KEY,
            community_id TEXT NOT NULL,
            local_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            queued_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
          )
        ''');
        await db.execute('CREATE INDEX idx_members_community ON members(community_id, full_name)');
      },
    );
    return _db!;
  }

  Future<List<Member>> search(String communityId, {String query = ''}) async {
    final db = await _database;
    final rows = query.isEmpty
        ? await db.query('members', where: 'community_id = ?', whereArgs: [communityId], orderBy: 'full_name')
        : await db.query(
            'members',
            where: 'community_id = ? AND (full_name LIKE ? OR phone LIKE ?)',
            whereArgs: [communityId, '%$query%', '%$query%'],
            orderBy: 'full_name',
          );
    return rows.map(Member.fromSqlite).toList();
  }

  Future<void> upsert(String communityId, Member member) async {
    final db = await _database;
    await db.insert('members', {...member.toSqlite(), 'community_id': communityId}, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertMany(String communityId, List<Member> members) async {
    final db = await _database;
    final batch = db.batch();
    for (final m in members) {
      batch.insert('members', {...m.toSqlite(), 'community_id': communityId}, conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  Future<void> deleteLocal(String communityId, String id) async {
    final db = await _database;
    await db.delete('members', where: 'id = ? AND community_id = ?', whereArgs: [id, communityId]);
  }

  Future<void> enqueue(String communityId, String opId, String localId, Map<String, dynamic> payload) async {
    final db = await _database;
    await db.insert('member_sync_queue', {
      'op_id': opId,
      'community_id': communityId,
      'local_id': localId,
      'payload': jsonEncode(payload),
      'queued_at': DateTime.now().toIso8601String(),
      'attempts': 0,
    });
  }

  Future<List<Map<String, dynamic>>> pendingOps(String communityId) async {
    final db = await _database;
    final rows = await db.query('member_sync_queue', where: 'community_id = ?', whereArgs: [communityId], orderBy: 'queued_at ASC');
    return rows.map((r) => {
          'op_id': r['op_id'],
          'local_id': r['local_id'],
          'payload': jsonDecode(r['payload'] as String) as Map<String, dynamic>,
        }).toList();
  }

  Future<void> markOpFailed(String opId, String error) async {
    final db = await _database;
    await db.rawUpdate('UPDATE member_sync_queue SET attempts = attempts + 1, last_error = ? WHERE op_id = ?', [error, opId]);
  }

  Future<void> removeOp(String opId) async {
    final db = await _database;
    await db.delete('member_sync_queue', where: 'op_id = ?', whereArgs: [opId]);
  }
}
