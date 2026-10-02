"use client";

import "@/styles/family-registry-tokens.css";
import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { documentsApi } from "@/lib/api/documents";
import { useFamilies } from "@/lib/hooks/useFamilies";

const KINDS: [string, string][] = [["minutes", "Meeting minutes"], ["statement", "Financial statement"], ["receipt", "Receipt / invoice"], ["register", "Register / list"], ["other", "Other"]];

/**
 * "All financial secretaries and all secretaries at all levels should be
 * able to upload or download files, PDF or Excel documents." Community
 * keepers see the community's and every family's records; a family's
 * keepers see only their own family's.
 */
export default function DocumentsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["documents"], queryFn: documentsApi.list });
  const { data: families } = useFamilies();
  const fileRef = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState(""); const [kind, setKind] = useState("other"); const [familyId, setFamilyId] = useState("");
  const upload = useMutation({
    mutationFn: () => { const f = fileRef.current?.files?.[0]; if (!f) throw new Error("Choose a file."); return documentsApi.upload(f, title, kind, familyId || undefined); },
    onSuccess: () => { setTitle(""); if (fileRef.current) fileRef.current.value = ""; qc.invalidateQueries({ queryKey: ["documents"] }); },
  });
  const remove = useMutation({ mutationFn: (id: string) => documentsApi.remove(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }) });

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b border-[var(--border)] bg-[var(--card)] px-8 py-6">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">{data?.level === "family" ? `${data.family_name} family records` : "Community records"}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Documents</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">Minutes, statements, spreadsheets, scanned receipts — PDF, Excel, CSV, Word, or images, up to 15 MB each.</p>
      </header>
      <main className="space-y-6 px-8 py-8">
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
        {data && (
          <section className="rounded-[var(--radius)] bg-[var(--card)] p-5" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
            <h2 className="text-lg font-semibold">Upload</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <input ref={fileRef} type="file" accept=".pdf,.xlsx,.xls,.csv,.docx,.doc,.png,.jpg,.jpeg" className="text-sm" />
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (optional — file name used if blank)" className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm" />
              <select value={kind} onChange={(e) => setKind(e.target.value)} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm">{KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              {data.level === "community" && (
                <select value={familyId} onChange={(e) => setFamilyId(e.target.value)} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"><option value="">Community-level</option>{(families ?? []).map((f) => <option key={f.id} value={f.id}>{f.name} family</option>)}</select>
              )}
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button onClick={() => upload.mutate()} disabled={upload.isPending} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{upload.isPending ? "Uploading…" : "Upload"}</button>
              {upload.isError && <span className="text-xs text-[var(--clay-red)]">{upload.error.message}</span>}
            </div>
          </section>
        )}
        <section className="rounded-[var(--radius)] bg-[var(--card)] p-5" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
          <h2 className="text-lg font-semibold">Files</h2>
          {isLoading && <p className="mt-2 text-sm text-[var(--text-soft)]">Loading…</p>}
          <ul className="mt-3 divide-y divide-[var(--border-soft)]">
            {(data?.documents ?? []).map((d) => (
              <li key={d.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5 text-sm">
                <div><p className="font-medium">{d.title}</p><p className="text-xs text-[var(--text-soft)]">{d.kind_label} · {d.family_name ? `${d.family_name} family` : "Community"} · {d.original_name} · {(d.size_bytes / 1024).toFixed(0)} KB · {d.uploaded_by_username ?? "—"} · {new Date(d.created_at).toLocaleDateString()}</p></div>
                <div className="flex gap-3">
                  <button onClick={() => documentsApi.download(d)} className="font-medium text-[var(--primary)] hover:underline">Download</button>
                  <button onClick={() => { if (window.confirm(`Remove "${d.title}"?`)) remove.mutate(d.id); }} className="text-[var(--clay-red)] hover:underline">Remove</button>
                </div>
              </li>
            ))}
            {data && data.documents.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">No documents yet.</li>}
          </ul>
          {remove.isError && <p className="mt-2 text-xs text-[var(--clay-red)]">{remove.error.message}</p>}
        </section>
      </main>
    </div>
  );
}
