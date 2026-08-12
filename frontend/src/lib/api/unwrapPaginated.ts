/**
 * Every list endpoint in the backend is paginated now (DRF's
 * PageNumberPagination — see nsaabodeeq/pagination.py and settings.py's
 * REST_FRAMEWORK config), so a JSON response that used to be a raw
 * array `[...]` is now an envelope: `{count, next, previous, results}`.
 *
 * This unwraps that envelope back to a plain array at the API-client
 * boundary, so every existing hook/component in this app keeps working
 * unchanged. That's a deliberate, honest trade-off, not a full fix:
 * it means the web frontend today only ever shows the FIRST PAGE (25
 * items) of any list — the backend enforces the boundary for real, but
 * there's no "load more" / infinite-scroll UI wired up yet to reach page
 * 2 and beyond. For Bodi's ~200 members that's rarely felt; a community
 * with thousands of members would need pagination controls added to the
 * relevant list pages (Members, Family Registry, obligation ledgers,
 * gift ledgers) as a real follow-up, not something to keep silently
 * papering over with a larger PAGE_SIZE.
 */
export function unwrapPaginated<T>(json: unknown): T[] {
  if (
    json &&
    typeof json === "object" &&
    Array.isArray((json as { results?: unknown }).results) &&
    typeof (json as { count?: unknown }).count === "number"
  ) {
    return (json as { results: T[] }).results;
  }
  return json as T[];
}
