import { authFetch } from "./authFetch";

export interface AnnouncementReviewLogEntry {
  action: string;
  actor_username: string | null;
  notes: string;
  created_at: string;
}

export interface Announcement {
  id: string;
  community: string;
  community_name: string;
  title: string;
  content: string;
  image_url: string | null;
  video_url: string;
  status: "pending" | "approved" | "rejected";
  submitted_by_username: string;
  submitted_at: string;
  reviewed_by_username: string | null;
  reviewed_at: string | null;
  rejection_reason: string;
  was_edited_by_reviewer: boolean;
  review_log: AnnouncementReviewLogEntry[];
  homepage_feature_requested: boolean;
  featured_on_homepage: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message = body.detail?.toString() ?? Object.values(body).flat().join(" ") ?? `Request failed (${res.status})`;
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

/**
 * "Any community who wants to post announcement on the notice board...
 * has to be submitted by the community admin and the super admin has
 * to approve it before... and the super admin can edit the content or
 * reject it with reasons for the community admin to edit and resend
 * again."
 */
export const announcementsApi = {
  noticeBoard: () => request<Announcement[]>(`/tenants/notice-board/`),

  /** "When it needs it on the homepage he has to send a request to the platform admin." Public — no login, matching the homepage itself. */
  homepageFeatured: async (): Promise<Announcement[]> => {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/tenants/notice-board/homepage-featured/`);
    if (!res.ok) return [];
    return res.json();
  },

  listOwnCommunity: (communityId: string) => request<Announcement[]>(`/tenants/communities/${communityId}/announcements/`),

  submit: (communityId: string, input: { title: string; content: string; image?: File; video_url?: string; homepage_feature_requested?: boolean }) => {
    const form = new FormData();
    form.set("title", input.title);
    form.set("content", input.content);
    if (input.image) form.set("image", input.image);
    if (input.video_url) form.set("video_url", input.video_url);
    if (input.homepage_feature_requested) form.set("homepage_feature_requested", "true");
    return authFetch(`/tenants/communities/${communityId}/announcements/submit/`, { method: "POST", body: form }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail?.toString() ?? "Could not submit this announcement.");
      }
      return res.json();
    });
  },

  resubmit: (announcementId: string, input: { title?: string; content?: string; video_url?: string }) =>
    request<Announcement>(`/tenants/announcements/${announcementId}/resubmit/`, { method: "POST", body: JSON.stringify(input) }),

  listPendingReview: () => request<Announcement[]>(`/tenants/announcements/pending-review/`),

  approve: (announcementId: string, input?: { edited_title?: string; edited_content?: string; feature_on_homepage?: boolean }) =>
    request<Announcement>(`/tenants/announcements/${announcementId}/approve/`, { method: "POST", body: JSON.stringify(input ?? {}) }),

  reject: (announcementId: string, reason: string) =>
    request<Announcement>(`/tenants/announcements/${announcementId}/reject/`, { method: "POST", body: JSON.stringify({ reason }) }),
};
