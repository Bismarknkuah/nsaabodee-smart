/**
 * Turns a raw role value into its display label. A single, small
 * override table rather than a role-by-role rename in the database.
 * The underlying role value stays exactly what it already is
 * everywhere else (permissions, the database, the API), since
 * renaming that would be a much larger, riskier migration for a
 * purely cosmetic change.
 */
const ROLE_DISPLAY_OVERRIDES: Record<string, string> = {
  bereaved_rep: "deceased rep",
  // Confirmed by the person: "the arrears collector for the
  // community and the community arrears officer are the same
  // role." Reads consistently alongside "family arrears officer"
  // and "town elders arrears officer", which already display
  // correctly through the plain underscore-to-space fallback below.
  arrears_collector: "community arrears officer",
};

/**
 * "Asona family head", "Bretuo secretary" — a family role carries the
 * family it serves, so the same title in two families is never confused.
 */
const FAMILY_ROLE_SUFFIX: Record<string, string> = {
  family_head: "family head",
  family_secretary: "secretary",
  family_treasurer: "treasurer",
  family_registration_officer: "registration officer",
  family_arrears_officer: "arrears officer",
};

export function formatRole(role: string | null | undefined, familyName?: string | null): string {
  if (!role) return "";
  if (familyName && FAMILY_ROLE_SUFFIX[role]) return `${familyName} ${FAMILY_ROLE_SUFFIX[role]}`;
  return ROLE_DISPLAY_OVERRIDES[role] ?? role.replace(/_/g, " ");
}

/** Prefer the server's family-qualified label when a user object carries one. */
export function formatRoleOf(user: { role?: string | null; role_label?: string | null } | null | undefined): string {
  if (!user) return "";
  return user.role_label ? user.role_label.toLowerCase() : formatRole(user.role);
}
