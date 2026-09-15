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

export function formatRole(role: string | null | undefined): string {
  if (!role) return "";
  return ROLE_DISPLAY_OVERRIDES[role] ?? role.replace(/_/g, " ");
}
