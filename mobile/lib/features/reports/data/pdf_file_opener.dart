import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

/// `getTemporaryDirectory()` (path_provider) and `File.writeAsBytes`
/// (dart:io) are both about as stable an API surface as Flutter has —
/// unlike the Bluetooth printer package elsewhere in this codebase,
/// there's nothing version-sensitive being guessed at here.
///
/// Actually opening the written file with the OS's own PDF viewer does
/// need a small platform-integration package (`open_filex` is suggested
/// in the pubspec snippet) — that one line (`OpenFilex.open(path)`) is
/// the one part of this utility worth double-checking against pub.dev's
/// current docs before relying on it, the same caveat as the Bluetooth
/// printer connection, just much smaller in scope.
class PdfFileOpener {
  static Future<String> save(Uint8List bytes, String filename) async {
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/$filename');
    await file.writeAsBytes(bytes, flush: true);
    return file.path;
  }

  static Future<void> saveAndOpen(Uint8List bytes, String filename) async {
    final path = await save(bytes, filename);
    // ignore: avoid_print
    print('Receipt PDF saved to $path — open with the platform file opener.');
    // Wire this up against whichever "open a file with the OS default
    // app" package the project settles on, e.g.:
    //   import 'package:open_filex/open_filex.dart';
    //   await OpenFilex.open(path);
    // Left as a clearly-marked stub rather than an unverified call,
    // since this specific call is the one part of this file I can't
    // confirm without running it.
    throw UnimplementedError(
      'Saved to $path. Wire up a file-opener package (e.g. open_filex) '
      'here to actually launch the OS PDF viewer — see this method\'s doc comment.',
    );
  }
}
