import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

import '../domain/family.dart';
import '../domain/family_sync_op.dart';

/// Local persistence for the Family Management Module. Runs entirely
/// offline; the repository layer decides when to read from here vs. the
/// network. Every community's data is namespaced by [communityId] so a
/// device that's ever logged into more than one community (e.g. a
/// platform admin, or a phone reused between two Bodi-style deployments)
/// never mixes their family lists.
class FamiliesLocalDb {
  static const _dbName = 'nsaabodee_families.db';
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
          CREATE TABLE families (
            id TEXT NOT NULL,
            community_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            family_head_id TEXT,
            family_head_name TEXT,
            member_count INTEGER NOT NULL DEFAULT 0,
            merged_into_id TEXT,
            updated_at TEXT NOT NULL,
            pending_sync INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (id, community_id)
          )
        ''');
        await db.execute('''
          CREATE TABLE family_sync_queue (
            op_id TEXT PRIMARY KEY,
            community_id TEXT NOT NULL,
            type TEXT NOT NULL,
            family_local_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            queued_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
          )
        ''');
        await db.execute(
          'CREATE INDEX idx_families_community ON families(community_id, status)',
        );
      },
    );
    return _db!;
  }

  Future<List<Family>> listFamilies(String communityId, {bool includeInactive = false}) async {
    final db = await _database;
    final where = includeInactive
        ? 'community_id = ?'
        : "community_id = ? AND status NOT IN ('deleted')";
    final rows = await db.query(
      'families',
      where: where,
      whereArgs: [communityId],
      orderBy: 'name COLLATE NOCASE ASC',
    );
    return rows.map(Family.fromSqlite).toList();
  }

  Future<void> upsertFamily(String communityId, Family family) async {
    final db = await _database;
    await db.insert(
      'families',
      {...family.toSqlite(), 'community_id': communityId},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<void> upsertMany(String communityId, List<Family> families) async {
    final db = await _database;
    final batch = db.batch();
    for (final f in families) {
      batch.insert(
        'families',
        {...f.toSqlite(), 'community_id': communityId},
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  Future<void> enqueue(String communityId, FamilySyncOp op) async {
    final db = await _database;
    await db.insert(
      'family_sync_queue',
      {...op.toSqlite(), 'community_id': communityId},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<List<FamilySyncOp>> pendingOps(String communityId) async {
    final db = await _database;
    final rows = await db.query(
      'family_sync_queue',
      where: 'community_id = ?',
      whereArgs: [communityId],
      orderBy: 'queued_at ASC',
    );
    return rows.map(FamilySyncOp.fromSqlite).toList();
  }

  Future<void> markOpFailed(String opId, String error) async {
    final db = await _database;
    await db.rawUpdate(
      'UPDATE family_sync_queue SET attempts = attempts + 1, last_error = ? WHERE op_id = ?',
      [error, opId],
    );
  }

  Future<void> removeOp(String opId) async {
    final db = await _database;
    await db.delete('family_sync_queue', where: 'op_id = ?', whereArgs: [opId]);
  }
}
