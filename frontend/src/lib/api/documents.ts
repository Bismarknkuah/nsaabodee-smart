import { authFetch } from "./authFetch";

export interface DocumentRow { id: string; title: string; kind: string; kind_label: string; original_name: string; size_bytes: number; family: string | null; family_name: string | null; uploaded_by_username: string | null; created_at: string }

/** "All financial secretaries and all secretaries at all levels should be able to upload or download files, PDF or Excel documents." */
export const documentsApi = {
  list: async () => {
    const res = await authFetch(`/documents/`);
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Couldn't load documents.");
    return res.json() as Promise<{ level: "community" | "family"; family_name: string | null; documents: DocumentRow[] }>;
  },
  upload: async (file: File, title: string, kind: string, familyId?: string) => {
    const form = new FormData();
    form.append("file", file); form.append("title", title); form.append("kind", kind);
    if (familyId) form.append("family_id", familyId);
    const res = await authFetch(`/documents/`, { method: "POST", body: form });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Upload failed.");
    return res.json() as Promise<DocumentRow>;
  },
  download: async (doc: DocumentRow) => {
    const res = await authFetch(`/documents/${doc.id}/`);
    if (!res.ok) throw new Error("Couldn't download.");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = doc.original_name || doc.title; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },
  remove: async (id: string) => {
    const res = await authFetch(`/documents/${id}/`, { method: "DELETE" });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Couldn't remove.");
  },
};
