class Member {
  final String id;
  final String membershipNumber;
  final String fullName;
  final String gender;
  final String? familyId;
  final String? familyName;
  final String phone;
  final String status;
  final String defaulterTier;
  final String? photoUrl;

  /// Path to a photo captured offline, not yet uploaded. Once synced,
  /// [photoUrl] is populated from the server and this is cleared — the
  /// two are never both meaningful at once.
  final String? pendingPhotoLocalPath;
  final bool pendingSync;

  const Member({
    required this.id,
    required this.membershipNumber,
    required this.fullName,
    required this.gender,
    required this.phone,
    required this.status,
    required this.defaulterTier,
    this.familyId,
    this.familyName,
    this.photoUrl,
    this.pendingPhotoLocalPath,
    this.pendingSync = false,
  });

  factory Member.fromApiJson(Map<String, dynamic> json) {
    final familyDetail = json['family_detail'] as Map<String, dynamic>?;
    return Member(
      id: json['id'] as String,
      membershipNumber: json['membership_number'] as String,
      fullName: json['full_name'] as String,
      gender: json['gender'] as String,
      familyId: json['family'] as String?,
      familyName: familyDetail?['name'] as String?,
      phone: json['phone'] as String? ?? '',
      status: json['status'] as String,
      defaulterTier: json['defaulter_tier'] as String,
      photoUrl: json['photo_url'] as String?,
      pendingSync: false,
    );
  }

  factory Member.fromSqlite(Map<String, dynamic> row) => Member(
        id: row['id'] as String,
        membershipNumber: row['membership_number'] as String,
        fullName: row['full_name'] as String,
        gender: row['gender'] as String,
        familyId: row['family_id'] as String?,
        familyName: row['family_name'] as String?,
        phone: row['phone'] as String? ?? '',
        status: row['status'] as String,
        defaulterTier: row['defaulter_tier'] as String,
        photoUrl: row['photo_url'] as String?,
        pendingPhotoLocalPath: row['pending_photo_local_path'] as String?,
        pendingSync: (row['pending_sync'] as int? ?? 0) == 1,
      );

  Map<String, dynamic> toSqlite() => {
        'id': id,
        'membership_number': membershipNumber,
        'full_name': fullName,
        'gender': gender,
        'family_id': familyId,
        'family_name': familyName,
        'phone': phone,
        'status': status,
        'defaulter_tier': defaulterTier,
        'photo_url': photoUrl,
        'pending_photo_local_path': pendingPhotoLocalPath,
        'pending_sync': pendingSync ? 1 : 0,
      };
}
