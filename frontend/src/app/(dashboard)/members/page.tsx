"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useMembers } from "@/lib/hooks/useMembers";
import { useFuzzySearch } from "@/lib/hooks/useAiFeatures";
import { RegisterMemberDialog } from "@/components/members/RegisterMemberDialog";
import { authFetch } from "@/lib/api/authFetch";
import type { DefaulterTier } from "@/types/member";

const TIER_COLOR: Record<DefaulterTier, string> = {
  none: "var(--forest)",
  warning: "var(--gold)",
  high_warning: "var(--gold)",
  flagged: "var(--clay-red)",
};

const TIER_LABEL: Record<DefaulterTier, string> = {
  none: "In good standing",
  warning: "Warning",
  high_warning: "High warning",
  flagged: "Flagged",
};

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: "name", label: "Name (A–Z)" },
  { value: "family", label: "Family" },
  { value: "age", label: "Age (oldest first)" },
  { value: "age_youngest_first", label: "Age (youngest first)" },
  { value: "gender", label: "Gender" },
  { value: "status", label: "Status" },
  { value: "membership_number", label: "Membership number" },
];

export default function MembersPage() {
  const [search, setSearch] = useState("");
  const [gender, setGender] = useState<"" | "male" | "female">("");
  const [sortBy, setSortBy] = useState("name");
  const [exporting, setExporting] = useState<"csv" | "pdf" | null>(null);
  const { data: members, isLoading } = useMembers({ search, gender: gender || undefined, sort_by: sortBy });
  const [showRegister, setShowRegister] = useState(false);
  const showFuzzy = search.trim().length >= 2 && !isLoading && (members?.length ?? 0) === 0;
  const { data: fuzzyResults } = useFuzzySearch(showFuzzy ? search : "");

  // 'All data should be downloaded or printable.' Family-scoped
  // automatically server-side for Family Head/Secretary/Treasurer —
  // matches exactly what this page already shows them, since both go
  // through the same members.services.search_members underneath.
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ created_count: number; error_count: number; errors: { row: number; full_name: string; error: string }[] } | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const qc = useQueryClient();

  const handleExport = async (format: "csv" | "pdf") => {
    setExporting(format);
    try {
      const res = await authFetch(`/reports/members/export/?export_format=${format}`);
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (format === "pdf") {
        window.open(url, "_blank");
      } else {
        const a = document.createElement("a");
        a.href = url;
        a.download = "members.csv";
        a.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } finally {
      setExporting(null);
    }
  };

  // 'Executive should have access to upload data when necessary.' A
  // Family Head or Secretary's CSV is automatically locked to their
  // own family server-side (bulk_register_members reuses register_member,
  // which already enforces this) regardless of any family_name column
  // in the file itself.
  const handleUpload = async (file: File) => {
    setUploading(true);
    setUploadResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await authFetch("/members/bulk-upload/", { method: "POST", body: formData });
      const data = await res.json();
      if (res.ok || res.status === 207) {
        setUploadResult(data);
        if (data.created_count > 0) qc.invalidateQueries({ queryKey: ["members"] });
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-6 py-6 sm:px-10">
        <div className="mx-auto flex max-w-6xl items-end justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
              Community Register · {members?.length ?? 0} listed
            </p>
            <h1 className="font-display mt-1 text-4xl">Members</h1>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <button
              onClick={() => handleExport("csv")}
              disabled={exporting !== null}
              className="border border-[var(--rule)] px-3 py-2 text-sm font-medium hover:border-[var(--ink)] disabled:opacity-60"
            >
              {exporting === "csv" ? "Preparing…" : "Export CSV"}
            </button>
            <button
              onClick={() => handleExport("pdf")}
              disabled={exporting !== null}
              className="border border-[var(--rule)] px-3 py-2 text-sm font-medium hover:border-[var(--ink)] disabled:opacity-60"
            >
              {exporting === "pdf" ? "Preparing…" : "Export PDF"}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="border border-[var(--rule)] px-3 py-2 text-sm font-medium hover:border-[var(--ink)] disabled:opacity-60"
            >
              {uploading ? "Uploading…" : "Upload CSV"}
            </button>
            <Link
              href="/members/defaulters"
              className="border border-[var(--clay-red)] px-4 py-2 text-sm font-medium text-[var(--clay-red)] hover:bg-[var(--clay-red-soft)]"
            >
              Defaulters
            </Link>
            <button
              onClick={() => setShowRegister(true)}
              className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Register member
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-5 sm:px-10">
        <div className="flex flex-wrap items-end gap-4">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, phone, or Ghana Card…"
            className="w-full max-w-md border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)] sm:w-80"
          />
          <div>
            <label className="block text-[10px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">Gender</label>
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value as "" | "male" | "female")}
              className="mt-1 rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm"
            >
              <option value="">All</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">Sort by</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="mt-1 rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {uploadResult && (
          <div className="mt-4 border border-[var(--rule)] bg-white p-4">
            <p className="text-sm font-medium">
              {uploadResult.created_count} member(s) registered
              {uploadResult.error_count > 0 && `, ${uploadResult.error_count} row(s) failed`}.
            </p>
            {uploadResult.errors.length > 0 && (
              <ul className="mt-2 space-y-1">
                {uploadResult.errors.map((e) => (
                  <li key={e.row} className="text-xs text-[var(--clay-red)]">
                    Row {e.row} ({e.full_name || "no name"}): {e.error}
                  </li>
                ))}
              </ul>
            )}
            <button onClick={() => setUploadResult(null)} className="mt-2 text-xs text-[var(--ink-soft)] hover:underline">
              Dismiss
            </button>
          </div>
        )}
      </div>

      <main className="mx-auto max-w-6xl px-6 pb-16 sm:px-10">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading members…</p>}

        {showFuzzy && fuzzyResults && fuzzyResults.length > 0 && (
          <div className="mb-4 border border-dashed border-[var(--rule)] bg-white p-4">
            <p className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">
              No exact match — did you mean
            </p>
            <ul className="mt-2 space-y-1">
              {fuzzyResults.map((r) => (
                <li key={r.member_id}>
                  <Link
                    href={`/members/${r.member_id}`}
                    className="text-sm text-[var(--forest)] hover:underline"
                  >
                    {r.full_name} <span className="font-mono text-xs text-[var(--ink-soft)]">({r.membership_number})</span>
                  </Link>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-[var(--ink-soft)]">
              Fuzzy text matching, not speech recognition — if you spoke this search aloud, your
              device&apos;s own dictation turned it into text first.
            </p>
          </div>
        )}

        <ul className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
          {members?.map((m, i) => (
            <li key={m.id}>
              <Link href={`/members/${m.id}`} className="flex items-center gap-4 py-3.5 hover:bg-white">
                <span className="w-8 shrink-0 font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(3, "0")}</span>
                {m.photo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={m.photo_url} alt="" className="h-10 w-10 rounded-full object-cover" />
                ) : (
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--surface)] font-display text-sm text-[var(--ink-soft)]">
                    {m.full_name.charAt(0)}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{m.full_name}</p>
                  <p className="font-mono text-xs text-[var(--ink-soft)]">
                    {m.membership_number} · {m.family_detail?.name ?? "No family"}
                  </p>
                </div>
                <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: TIER_COLOR[m.defaulter_tier] }}>
                  <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: TIER_COLOR[m.defaulter_tier] }} />
                  {TIER_LABEL[m.defaulter_tier]}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </main>

      {showRegister && <RegisterMemberDialog onClose={() => setShowRegister(false)} />}
    </div>
  );
}
