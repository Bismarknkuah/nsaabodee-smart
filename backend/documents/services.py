import os

from django.core.exceptions import ValidationError

from .models import Document

# Who keeps the files, at each level. Community: the Secretary and the
# Financial Secretary (Admin and Chairman may also read and add). Family:
# the family's Secretary and Treasurer (the Head may read and add). Town
# Elders: the Town Registration Officer keeps the elders' records under the
# community scope, and the Chief may read.
COMMUNITY_DOCUMENT_ROLES = {"community_admin", "chairman", "secretary", "financial_secretary", "town_registration_officer", "traditional_leader"}
FAMILY_DOCUMENT_ROLES = {"family_head", "family_secretary", "family_treasurer"}
LEGACY_ALIASES = {"treasurer": "financial_secretary", "auditor": "financial_secretary", "notification_officer": "secretary", "community_registration_desk": "secretary", "family_registration_officer": "family_secretary"}


def _effective_role(user):
    return LEGACY_ALIASES.get(user.role, user.role)


def document_scope(user):
    """(level, family) the user may read and write in — 'community', ('family', Family), or None."""
    if user.is_superuser or _effective_role(user) in COMMUNITY_DOCUMENT_ROLES:
        return ("community", None)
    if _effective_role(user) in FAMILY_DOCUMENT_ROLES:
        member = getattr(user, "member_profile", None)
        if member is not None and member.family_id:
            return ("family", member.family)
    return None


def visible_documents(*, user):
    scope = document_scope(user)
    if scope is None:
        return Document.objects.none()
    level, family = scope
    qs = Document.objects.filter(community=user.community).select_related("family", "uploaded_by")
    if level == "family":
        return qs.filter(family=family)
    return qs  # community-level keepers see the community's and every family's records


def can_download(user, document) -> bool:
    return visible_documents(user=user).filter(id=document.id).exists()


def upload_document(*, user, upload, title: str, kind: str = Document.Kind.OTHER, family=None) -> Document:
    scope = document_scope(user)
    if scope is None:
        raise ValidationError("Your role does not keep documents.")
    level, own_family = scope
    if level == "family":
        family = own_family  # a family keeper only ever files into their own family
    elif family is not None and family.community_id != user.community_id:
        raise ValidationError("That family is not in your community.")
    name = getattr(upload, "name", "") or ""
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    if ext not in Document.ALLOWED_EXTENSIONS:
        raise ValidationError(f"'.{ext or '?'}' files are not accepted. Use PDF, Excel, CSV, Word, or an image.")
    size = getattr(upload, "size", 0) or 0
    if size > Document.MAX_BYTES:
        raise ValidationError("That file is larger than 15 MB.")
    if not (title or "").strip():
        title = os.path.splitext(name)[0] or "Untitled"
    valid_kinds = {c for c, _ in Document.Kind.choices}
    return Document.objects.create(
        community=user.community, family=family, title=title.strip()[:200], kind=kind if kind in valid_kinds else Document.Kind.OTHER,
        file=upload, original_name=name[:255], size_bytes=size, uploaded_by=user,
    )


def delete_document(*, user, document):
    if not can_download(user, document):
        raise ValidationError("You cannot remove this document.")
    if document.uploaded_by_id != user.id and _effective_role(user) not in ("community_admin", "chairman", "family_head"):
        raise ValidationError("Only whoever uploaded a document, or the head of that level, can remove it.")
    document.file.delete(save=False)
    document.delete()
