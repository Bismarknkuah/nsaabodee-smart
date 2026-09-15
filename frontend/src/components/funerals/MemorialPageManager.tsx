"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { funeralsApi } from "@/lib/api/funerals";

/**
 * "A dignified public page for the funeral... a lasting place to
 * remember your loved one." Lives on the funeral detail page, visible
 * only to whoever can actually manage it (the backend enforces this —
 * a 403 here just means don't show the panel, not that anything is
 * actually protected by hiding it).
 */
export function MemorialPageManager({ funeralId }: { funeralId: string }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [tributeMessage, setTributeMessage] = useState("");
  const [keyDetails, setKeyDetails] = useState("");
  const [showDraftHelper, setShowDraftHelper] = useState(false);
  const [showTotal, setShowTotal] = useState(false);
  const [isPublished, setIsPublished] = useState(true);
  const [saved, setSaved] = useState(false);

  const { data: tributes, isError } = useQuery({
    queryKey: ["memorial-tributes-manage", funeralId],
    queryFn: () => funeralsApi.listTributesForManagement(funeralId),
    enabled: expanded,
    retry: false,
  });

  const save = useMutation({
    mutationFn: () => funeralsApi.manageMemorialPage(funeralId, { tribute_message: tributeMessage, show_contribution_total: showTotal, is_published: isPublished }),
    onSuccess: () => setSaved(true),
  });
  const draftTribute = useMutation({
    mutationFn: () => funeralsApi.draftTribute(funeralId, keyDetails),
    onSuccess: (result) => { setTributeMessage(result.draft); setShowDraftHelper(false); },
  });
  const approve = useMutation({
    mutationFn: (tributeId: string) => funeralsApi.approveTribute(funeralId, tributeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memorial-tributes-manage", funeralId] }),
  });
  const remove = useMutation({
    mutationFn: (tributeId: string) => funeralsApi.removeTribute(funeralId, tributeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["memorial-tributes-manage", funeralId] }),
  });

  if (isError) return null; // not permitted to manage this funeral's memorial page

  if (!expanded) {
    return (
      <button onClick={() => setExpanded(true)} className="mt-3 text-xs text-[var(--forest)] hover:underline">
        Manage memorial page
      </button>
    );
  }

  const pending = tributes?.filter((t) => !t.is_approved) ?? [];
  const approved = tributes?.filter((t) => t.is_approved) ?? [];

  return (
    <div className="mt-3 rounded-sm bg-[var(--surface)] p-3">
      <p className="text-xs text-[var(--ink-soft)]">
        A public page anyone can view without logging in — visitors can leave a tribute,
        which only shows up here once you approve it.
      </p>

      <div className="mt-3 space-y-2">
        <textarea
          value={tributeMessage}
          onChange={(e) => setTributeMessage(e.target.value)}
          placeholder="A tribute message, e.g. 'In loving memory of...'"
          rows={2}
          className="w-full rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-xs outline-none focus:border-[var(--forest)]"
        />
        {!showDraftHelper ? (
          <button type="button" onClick={() => setShowDraftHelper(true)} className="text-xs text-[var(--violet)] hover:underline">
            ✨ Draft this with AI, from a few details
          </button>
        ) : (
          <div className="rounded-sm border border-dashed border-[var(--violet)] bg-white p-2">
            <label className="text-xs font-medium text-[var(--ink-soft)]">
              Share a few real details — their character, what they loved, their work, their family.
              This drafts a genuine starting point; nothing is invented and nothing saves until you review and click Save below.
            </label>
            <textarea
              value={keyDetails}
              onChange={(e) => setKeyDetails(e.target.value)}
              placeholder="e.g. A devoted farmer and church elder, known for his warmth and generosity, survived by 5 children."
              rows={2}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-xs outline-none focus:border-[var(--violet)]"
            />
            <div className="mt-1.5 flex items-center gap-2">
              <button
                type="button"
                onClick={() => draftTribute.mutate()}
                disabled={draftTribute.isPending || !keyDetails.trim()}
                className="rounded-sm bg-[var(--violet)] px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50"
              >
                {draftTribute.isPending ? "Drafting…" : "Draft it"}
              </button>
              <button type="button" onClick={() => setShowDraftHelper(false)} className="text-xs text-[var(--ink-soft)] hover:underline">
                Cancel
              </button>
            </div>
            {draftTribute.isError && <p className="mt-1 text-xs text-[var(--clay-red)]">{draftTribute.error.message}</p>}
          </div>
        )}
        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" checked={showTotal} onChange={(e) => setShowTotal(e.target.checked)} />
          Show total contributions publicly (never individual donors or amounts)
        </label>
        <label className="flex items-center gap-2 text-xs">
          <input type="checkbox" checked={isPublished} onChange={(e) => setIsPublished(e.target.checked)} />
          Published (visible to anyone with the link)
        </label>
        <div className="flex items-center gap-2">
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
          >
            {save.isPending ? "Saving…" : "Save"}
          </button>
          {saved && <span className="text-xs" style={{ color: "var(--forest)" }}>Saved.</span>}
        </div>
      </div>

      {pending.length > 0 && (
        <div className="mt-4 border-t border-[var(--rule)] pt-3">
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Pending tributes</p>
          <ul className="mt-2 space-y-2">
            {pending.map((t) => (
              <li key={t.id} className="rounded-sm bg-white p-2 text-xs">
                <p>{t.message}</p>
                <p className="mt-1 text-[var(--ink-soft)]">— {t.author_name}</p>
                <div className="mt-1.5 flex gap-2">
                  <button onClick={() => approve.mutate(t.id)} className="text-[var(--forest)] hover:underline">Approve</button>
                  <button onClick={() => remove.mutate(t.id)} className="text-[var(--clay-red)] hover:underline">Remove</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {approved.length > 0 && (
        <div className="mt-4 border-t border-[var(--rule)] pt-3">
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Approved ({approved.length})</p>
          <ul className="mt-2 space-y-1">
            {approved.map((t) => (
              <li key={t.id} className="text-xs text-[var(--ink-soft)]">— {t.author_name}</li>
            ))}
          </ul>
        </div>
      )}

      <button onClick={() => setExpanded(false)} className="mt-3 text-xs text-[var(--ink-soft)]">Close</button>
    </div>
  );
}
