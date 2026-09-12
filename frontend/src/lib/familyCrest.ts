/**
 * Every family gets a small colored "crest tab" next to its name in the
 * registry, derived deterministically from the family's own id — never
 * chosen by hand, never random on reload, and never configurable, so it
 * stays a reliable scan cue ("oh, that's the teal-tab family") rather than
 * a decoration someone has to maintain.
 */
const CREST_PALETTE = [
  "#2B6E4E", // forest
  "#B8892B", // gold
  "#7A4B8C", // muted violet
  "#2E6E86", // teal-blue
  "#A9532E", // burnt sienna
  "#4B6E2B", // olive
  "#8C4B6B", // mulberry
  "#2B5C6E", // slate teal
];

export function crestColorFor(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return CREST_PALETTE[hash % CREST_PALETTE.length];
}
