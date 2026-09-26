import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

import '../domain/funeral_event.dart';
import '../domain/funeral_sync_op.dart';

class FuneralsLocalDb {
  static const _dbName = 'nsaabodee_funerals.db';
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
          CREATE TABLE funerals (
            id TEXT NOT NULL,
            community_id TEXT NOT NULL,
            deceased_name TEXT NOT NULL,
            deceased_gender TEXT NOT NULL,
            deceased_family_id TEXT NOT NULL,
            deceased_family_name TEXT NOT NULL,
            date_of_death TEXT NOT NULL,
            collection_start_date TEXT NOT NULL,
            status TEXT NOT NULL,
            own_family_amount TEXT NOT NULL,
            general_male_amount TEXT NOT NULL,
            general_female_amount TEXT NOT NULL,
            pending_sync INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (id, community_id)
          )
        ''');
        await db.execute('''
          CREATE TABLE obligations (
            id TEXT NOT NULL,
            community_id TEXT NOT NULL,
            funeral_event_id TEXT NOT NULL,
            member_id TEXT NOT NULL,
            member_name TEXT NOT NULL,
            rate_type TEXT NOT NULL,
            expected_amount TEXT NOT NULL,
            amount_paid TEXT NOT NULL,
            last_synced_payment_id TEXT,
            PRIMARY KEY (id, community_id)
          )
        ''');
        await db.execute('''
          CREATE TABLE funeral_sync_queue (
            op_id TEXT PRIMARY KEY,
            community_id TEXT NOT NULL,
            type TEXT NOT NULL,
            target_local_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            queued_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
          )
        ''');
        await db.execute('CREATE INDEX idx_funerals_community ON funerals(community_id, status)');
        await db.execute('CREATE INDEX idx_obligations_funeral ON obligations(funeral_event_id)');
      },
    );
    return _db!;
  }

  Future<List<FuneralEvent>> listFunerals(String communityId, {String status = 'active'}) async {
    final db = await _database;
    final rows = await db.query(
      'funerals',
      where: 'community_id = ? AND status = ?',
      whereArgs: [communityId, status],
      orderBy: 'date_of_death DESC',
    );
    return rows.map(FuneralEvent.fromSqlite).toList();
  }

  Future<void> upsertFuneral(String communityId, FuneralEvent funeral) async {
    final db = await _database;
    await db.insert('funerals', {...funeral.toSqlite(), 'community_id': communityId},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertManyFunerals(String communityId, List<FuneralEvent> funerals) async {
    final db = await _database;
    final batch = db.batch();
    for (final f in funerals) {
      batch.insert('funerals', {...f.toSqlite(), 'community_id': communityId},
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  Future<List<ContributionObligation>> listObligations(String funeralId) async {
    final db = await _database;
    final rows = await db.query('obligations', where: 'funeral_event_id = ?', whereArgs: [funeralId]);
    return rows.map(ContributionObligation.fromSqlite).toList();
  }

  Future<void> upsertManyObligations(String communityId, List<ContributionObligation> obligations) async {
    final db = await _database;
    final batch = db.batch();
    for (final o in obligations) {
      batch.insert('obligations', {...o.toSqlite(), 'community_id': communityId},
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  Future<void> recordLocalPayment(String obligationId, double amount) async {
    final db = await _database;
    final rows = await db.query('obligations', where: 'id = ?', whereArgs: [obligationId]);
    if (rows.isEmpty) return;
    final current = double.tryParse(rows.first['amount_paid'] as String) ?? 0;
    await db.update(
      'obligations',
      {'amount_paid': (current + amount).toStringAsFixed(2)},
      where: 'id = ?',
      whereArgs: [obligationId],
    );
  }

  Future<void> setLastSyncedPaymentId(String obligationId, String paymentId) async {
    final db = await _database;
    await db.update('obligations', {'last_synced_payment_id': paymentId}, where: 'id = ?', whereArgs: [obligationId]);
  }

  Future<String?> getLastSyncedPaymentId(String obligationId) async {
    final db = await _database;
    final rows = await db.query('obligations', columns: ['last_synced_payment_id'], where: 'id = ?', whereArgs: [obligationId]);
    if (rows.isEmpty) return null;
    return rows.first['last_synced_payment_id'] as String?;
  }

  Future<void> deleteFuneral(String communityId, String id) async {
    final db = await _database;
    await db.delete('funerals', where: 'id = ? AND community_id = ?', whereArgs: [id, communityId]);
  }

  Future<void> enqueue(String communityId, FuneralSyncOp op) async {
    final db = await _database;
    await db.insert('funeral_sync_queue', {...op.toSqlite(), 'community_id': communityId},
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<List<FuneralSyncOp>> pendingOps(String communityId) async {
    final db = await _database;
    final rows = await db.query('funeral_sync_queue', where: 'community_id = ?', whereArgs: [communityId], orderBy: 'queued_at ASC');
    return rows.map(FuneralSyncOp.fromSqlite).toList();
  }

  Future<void> markOpFailed(String opId, String error) async {
    final db = await _database;
    await db.rawUpdate(
      'UPDATE funeral_sync_queue SET attempts = attempts + 1, last_error = ? WHERE op_id = ?',
      [error, opId],
    );
  }

  Future<void> removeOp(String opId) async {
    final db = await _database;
    await db.delete('funeral_sync_queue', where: 'op_id = ?', whereArgs: [opId]);
  }
}
