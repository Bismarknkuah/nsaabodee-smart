import { describe, it, expect } from "vitest";
import { extractMemberIdFromScan } from "@/components/QrScannerModal";

/**
 * "Printing of receipt should have a bar code scanner." Every member's
 * qr_payload is "{FRONTEND_BASE_URL}/members/{id}" (see
 * members/models.py) — this is the parsing half of scanning that code
 * back at the Front Desk, and it has to correctly reject anything that
 * isn't actually one of this platform's own member QR codes, not just
 * correctly accept the real ones.
 */
describe("extractMemberIdFromScan", () => {
  const realMemberId = "a1b2c3d4-e5f6-4789-abcd-ef0123456789";

  it("extracts the member id from a real qr_payload URL", () => {
    expect(extractMemberIdFromScan(`https://app.nsaabodeesmart.com/members/${realMemberId}`)).toBe(realMemberId);
  });

  it("extracts the id with a trailing slash", () => {
    expect(extractMemberIdFromScan(`https://app.nsaabodeesmart.com/members/${realMemberId}/`)).toBe(realMemberId);
  });

  it("extracts the id from a localhost dev URL too", () => {
    expect(extractMemberIdFromScan(`http://localhost:3000/members/${realMemberId}`)).toBe(realMemberId);
  });

  it("returns null for an unrelated URL", () => {
    expect(extractMemberIdFromScan("https://example.com/totally-unrelated")).toBeNull();
  });

  it("returns null for a URL missing the id entirely", () => {
    expect(extractMemberIdFromScan("https://app.nsaabodeesmart.com/members/")).toBeNull();
  });

  it("returns null for plain text that isn't a URL at all", () => {
    expect(extractMemberIdFromScan("just some random scanned text")).toBeNull();
  });

  it("returns null for a member id that is not a real UUID shape", () => {
    expect(extractMemberIdFromScan("https://app.nsaabodeesmart.com/members/not-a-real-id")).toBeNull();
  });
});
