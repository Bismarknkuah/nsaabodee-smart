import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';

enum PrinterKind { network, bluetooth }

class PrinterPreference {
  final PrinterKind kind;
  final String address; // "host:port" for network, device address for Bluetooth
  final String label;

  const PrinterPreference({required this.kind, required this.address, required this.label});
}

/// A single saved printer preference per device — deliberately simple
/// (one row, always overwritten) since a collector's phone realistically
/// has one printer paired to it at a time, not a list to manage.
class PrinterPreferencesLocalDb {
  static const _dbName = 'nsaabodee_printer_prefs.db';

  Database? _db;

  Future<Database> get _database async {
    if (_db != null) return _db!;
    final path = join(await getDatabasesPath(), _dbName);
    _db = await openDatabase(
      path,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE printer_preference (
            id INTEGER PRIMARY KEY CHECK (id = 0),
            kind TEXT NOT NULL,
            address TEXT NOT NULL,
            label TEXT NOT NULL
          )
        ''');
      },
    );
    return _db!;
  }

  Future<void> save(PrinterPreference pref) async {
    final db = await _database;
    await db.insert(
      'printer_preference',
      {'id': 0, 'kind': pref.kind.name, 'address': pref.address, 'label': pref.label},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<PrinterPreference?> get() async {
    final db = await _database;
    final rows = await db.query('printer_preference', where: 'id = 0');
    if (rows.isEmpty) return null;
    final row = rows.first;
    return PrinterPreference(
      kind: PrinterKind.values.byName(row['kind'] as String),
      address: row['address'] as String,
      label: row['label'] as String,
    );
  }

  Future<void> clear() async {
    final db = await _database;
    await db.delete('printer_preference', where: 'id = 0');
  }
}
