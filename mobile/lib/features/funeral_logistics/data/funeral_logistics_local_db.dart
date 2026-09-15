import 'dart:convert';

import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

import '../domain/funeral_logistics_models.dart';

/// Expenses and attendance share a database file (unlike gifts, which
/// gets its own file to enforce ledger separation) because neither is a
/// financial ledger being confused with another — they're operational
/// records about a funeral, tracked together here purely for convenience.
class FuneralLogisticsLocalDb {
  static const _dbName = 'nsaabodee_funeral_logistics.db';
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
          CREATE TABLE expenses (
            id TEXT PRIMARY KEY,
            funeral_event_id TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            amount TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            voucher_number TEXT NOT NULL,
            incurred_on TEXT NOT NULL,
            pending_sync INTEGER NOT NULL DEFAULT 0
          )
        ''');
        await db.execute('''
          CREATE TABLE attendance (
            id TEXT PRIMARY KEY,
            funeral_event_id TEXT NOT NULL,
            member_id TEXT,
            display_name TEXT NOT NULL,
            pending_sync INTEGER NOT NULL DEFAULT 0
          )
        ''');
        await db.execute('''
          CREATE TABLE logistics_sync_queue (
            op_id TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            local_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            queued_at TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT
          )
        ''');
        await db.execute('CREATE INDEX idx_expenses_funeral ON expenses(funeral_event_id)');
        await db.execute('CREATE INDEX idx_attendance_funeral ON attendance(funeral_event_id)');
      },
    );
    return _db!;
  }

  // --- Expenses ---------------------------------------------------------

  Future<List<FuneralExpense>> listExpenses(String funeralId) async {
    final db = await _database;
    final rows = await db.query('expenses', where: 'funeral_event_id = ?', whereArgs: [funeralId], orderBy: 'incurred_on DESC');
    return rows.map(FuneralExpense.fromSqlite).toList();
  }

  Future<void> upsertExpense(FuneralExpense expense) async {
    final db = await _database;
    await db.insert('expenses', expense.toSqlite(), conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertManyExpenses(List<FuneralExpense> expenses) async {
    final db = await _database;
    final batch = db.batch();
    for (final e in expenses) {
      batch.insert('expenses', e.toSqlite(), conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  Future<void> deleteLocalExpense(String id) async {
    final db = await _database;
    await db.delete('expenses', where: 'id = ?', whereArgs: [id]);
  }

  // --- Attendance ---------------------------------------------------------

  Future<List<FuneralAttendanceRecord>> listAttendance(String funeralId) async {
    final db = await _database;
    final rows = await db.query('attendance', where: 'funeral_event_id = ?', whereArgs: [funeralId], orderBy: 'rowid DESC');
    return rows.map(FuneralAttendanceRecord.fromSqlite).toList();
  }

  Future<void> upsertAttendance(FuneralAttendanceRecord record) async {
    final db = await _database;
    await db.insert('attendance', record.toSqlite(), conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> upsertManyAttendance(List<FuneralAttendanceRecord> records) async {
    final db = await _database;
    final batch = db.batch();
    for (final r in records) {
      batch.insert('attendance', r.toSqlite(), conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  Future<void> deleteLocalAttendance(String id) async {
    final db = await _database;
    await db.delete('attendance', where: 'id = ?', whereArgs: [id]);
  }

  // --- Sync queue (shared, distinguished by `kind`) ----------------------

  Future<void> enqueue(String opId, String kind, String localId, Map<String, dynamic> payload) async {
    final db = await _database;
    await db.insert('logistics_sync_queue', {
      'op_id': opId,
      'kind': kind,
      'local_id': localId,
      'payload': jsonEncode(payload),
      'queued_at': DateTime.now().toIso8601String(),
      'attempts': 0,
    });
  }

  Future<List<Map<String, dynamic>>> pendingOps() async {
    final db = await _database;
    final rows = await db.query('logistics_sync_queue', orderBy: 'queued_at ASC');
    return rows.map((r) => {
          'op_id': r['op_id'],
          'kind': r['kind'],
          'local_id': r['local_id'],
          'payload': jsonDecode(r['payload'] as String) as Map<String, dynamic>,
        }).toList();
  }

  Future<void> markOpFailed(String opId, String error) async {
    final db = await _database;
    await db.rawUpdate('UPDATE logistics_sync_queue SET attempts = attempts + 1, last_error = ? WHERE op_id = ?', [error, opId]);
  }

  Future<void> removeOp(String opId) async {
    final db = await _database;
    await db.delete('logistics_sync_queue', where: 'op_id = ?', whereArgs: [opId]);
  }
}
