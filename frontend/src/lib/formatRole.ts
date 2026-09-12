/**
 * Turns a raw role value into its display label. A single, small
 * override table rather than a role-by-role rename in the database —
 * the underlying role value stays exactly "bereaved_rep" everywhere
 * else (permissions, the database, the API) since renaming that would
 * be a much larger, riskier migration for a purely cosmetic change.
 */
const ROLE_DISPLAY_OVERRIDES: Record<string, string> = {
  bereaved_rep: "deceased rep",
};

export function formatRole(role: string | null | undefined): string {
  if (!role) return "";
  return ROLE_DISPLAY_OVERRIDES[role] ?? role.replace(/_/g, " ");
}
