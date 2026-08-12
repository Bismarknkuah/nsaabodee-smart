"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { announcementsApi } from "@/lib/api/announcements";
import { useAuthStore } from "@/store/authStore";

/**
 * "Any community who wants to post announcement on the notice board...
 * has to be submitted by the community admin and the super admin has
 * to approve it before... and the super admin can edit the content or
 * reject it with reasons for the community admin to edit and resend
 * again." Everyone sees the approved board; only a Community Admin
 * sees the submission form and their own community's tracking panel
 * below it.
 */
export default function NoticeBoardPage() {
  const user = useAuthStore((s) => s.user);
  const isCommunityAdmin = user?.role === "community_admin" && user.community;

  const { data: board, isLoading } = useQuery({ queryKey: ["notice-board"], queryFn: announcementsApi.noticeBoard });

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Platform-wide</p>
        <h1 className="font-display mt-1 text-4xl">Notice Board</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Approved announcements from every community, most recent first.
        </p>
      </header>

      <main className="mx-auto max-w-3xl px-8 py-8">
        {isCommunityAdmin && <SubmitAnnouncementSection communityId={user!.community!} />}

        <h2 className="font-display mt-8 text-xl">Announcements</h2>
        {isLoading && <p className="mt-2 text-sm text-[var(--ink-soft)]">Loading…</p>}
        {board?.length === 0 && <p className="mt-2 text-sm text-[var(--ink-soft)]">Nothing posted yet.</p>}
        <ul className="mt-4 space-y-4">
          {board?.map((a) => (
            <li key={a.id} className="rounded-sm border border-[var(--rule)] bg-white p-6">
              <p className="font-mono text-xs uppercase tracking-wide text-[var(--ink-soft)]">{a.community_name}</p>
              <h3 className="font-display mt-1 text-xl">{a.title}</h3>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{a.content}</p>
              {a.image_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={a.image_url} alt="" className="mt-3 max-h-80 w-full rounded-sm object-cover" />
              )}
              {a.video_url && (
                <a href={a.video_url} target="_blank" rel="noreferrer" className="mt-3 inline-block text-sm text-[var(--forest)] hover:underline">
                  Watch video →
                </a>
              )}
              <p className="mt-3 text-xs text-[var(--ink-soft)]">Posted {new Date(a.submitted_at).toLocaleDateString()}</p>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}

function SubmitAnnouncementSection({ communityId }: { communityId: string }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [homepageFeatureRequested, setHomepageFeatureRequested] = useState(false);
  const [resubmitDrafts, setResubmitDrafts] = useState<Record<string, string>>({});

  const { data: own } = useQuery({ queryKey: ["own-announcements", communityId], queryFn: () => announcementsApi.listOwnCommunity(communityId) });

  const submit = useMutation({
    mutationFn: () => announcementsApi.submit(communityId, { title, content, image: image ?? undefined, video_url: videoUrl || undefined, homepage_feature_requested: homepageFeatureRequested }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["own-announcements", communityId] });
      setTitle(""); setContent(""); setVideoUrl(""); setImage(null); setHomepageFeatureRequested(false);
    },
  });

  const resubmit = useMutation({
    mutationFn: ({ id, content }: { id: string; content: string }) => announcementsApi.resubmit(id, { content }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["own-announcements", communityId] });
      qc.invalidateQueries({ queryKey: ["notice-board"] });
    },
  });

  const pending = own?.filter((a) => a.status === "pending") ?? [];
  const rejected = own?.filter((a) => a.status === "rejected") ?? [];
  const approved = own?.filter((a) => a.status === "approved") ?? [];

  return (
    <section className="rounded-sm border border-[var(--rule)] bg-white p-6">
      <h2 className="font-display text-xl">Submit an announcement</h2>
      <p className="mt-1 text-sm text-[var(--ink-soft)]">
        Reviewed by a platform administrator before it appears on the board — they may approve
        it as-is, make a small edit and approve it, or send it back with a reason.
      </p>

      <form onSubmit={(e) => { e.preventDefault(); submit.mutate(); }} className="mt-4 space-y-3">
        <input
          value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title"
          className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
        />
        <textarea
          value={content} onChange={(e) => setContent(e.target.value)} placeholder="Announcement content" rows={3}
          className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
        />
        <div className="flex flex-wrap gap-2">
          <input type="file" accept="image/*" onChange={(e) => setImage(e.target.files?.[0] ?? null)} className="text-sm" />
          <input
            value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} placeholder="Video link (YouTube, Vimeo, optional)"
            className="flex-1 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-[var(--ink-soft)]">
          <input type="checkbox" checked={homepageFeatureRequested} onChange={(e) => setHomepageFeatureRequested(e.target.checked)} />
          Also request this be featured on the public homepage — a platform administrator decides.
        </label>
        {submit.isError && <p className="text-sm text-[var(--clay-red)]">{(submit.error as Error).message}</p>}
        <button
          type="submit" disabled={submit.isPending || !title.trim() || !content.trim()}
          className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {submit.isPending ? "Submitting…" : "Submit for review"}
        </button>
      </form>

      {pending.length > 0 && (
        <div className="mt-6 border-t border-[var(--rule)] pt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Awaiting review</p>
          {pending.map((a) => (
            <p key={a.id} className="mt-1 text-sm">{a.title}</p>
          ))}
        </div>
      )}

      {rejected.length > 0 && (
        <div className="mt-6 border-t border-[var(--rule)] pt-4">
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--clay-red)]">Rejected — needs your attention</p>
          {rejected.map((a) => (
            <div key={a.id} className="mt-2 rounded-sm bg-[var(--clay-red-soft,#f6e6e3)] p-3">
              <p className="text-sm font-medium">{a.title}</p>
              <p className="mt-1 text-xs text-[var(--clay-red)]">Reason: {a.rejection_reason}</p>
              <textarea
                defaultValue={a.content}
                onChange={(e) => setResubmitDrafts((d) => ({ ...d, [a.id]: e.target.value }))}
                rows={2}
                className="mt-2 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-xs"
              />
              <button
                onClick={() => resubmit.mutate({ id: a.id, content: resubmitDrafts[a.id] ?? a.content })}
                className="mt-1.5 rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white"
              >
                Edit &amp; resend
              </button>
            </div>
          ))}
        </div>
      )}

      {approved.length > 0 && (
        <p className="mt-6 border-t border-[var(--rule)] pt-4 text-xs text-[var(--ink-soft)]">
          {approved.length} of your announcements are live on the board.
        </p>
      )}
    </section>
  );
}
