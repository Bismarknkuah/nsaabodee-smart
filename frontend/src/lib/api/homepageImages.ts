const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
import { authFetch } from "./authFetch";

export interface HomepageImage {
  id: string;
  image_url: string | null;
  video_url: string | null;
  caption: string;
  subcaption: string;
  display_order: number;
  is_active: boolean;
  created_at: string;
}

/**
 * "The homepage live pictures which will be changing should be
 * uploaded by the super admin." The public list is deliberately plain
 * fetch() — the homepage itself needs no login, so neither does this.
 */
export const homepageImagesApi = {
  listPublic: async (): Promise<HomepageImage[]> => {
    const res = await fetch(`${BASE}/api/tenants/homepage-images/`);
    if (!res.ok) return [];
    return res.json();
  },

  listAll: async (): Promise<HomepageImage[]> => {
    const res = await authFetch("/tenants/homepage-images/manage/");
    if (!res.ok) throw new Error("Could not load homepage images.");
    return res.json();
  },

  /** "Should be able to upload videos as well." Pass exactly one of image/video, never both — a slide is either a photo or a video. */
  upload: async (input: { image?: File; video?: File; caption?: string; subcaption?: string; display_order?: number }): Promise<HomepageImage> => {
    const form = new FormData();
    if (input.image) form.set("image", input.image);
    if (input.video) form.set("video", input.video);
    if (input.caption) form.set("caption", input.caption);
    if (input.subcaption) form.set("subcaption", input.subcaption);
    if (input.display_order !== undefined) form.set("display_order", String(input.display_order));
    const res = await authFetch("/tenants/homepage-images/manage/", { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? "Could not upload this slide.");
    }
    return res.json();
  },

  /** "The platform admin should have option to edit... caption." Caption/subcaption/ordering only — swapping the actual file is a new upload. */
  update: async (imageId: string, input: { caption?: string; subcaption?: string; display_order?: number }): Promise<HomepageImage> => {
    const res = await authFetch(`/tenants/homepage-images/${imageId}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!res.ok) throw new Error("Could not edit this slide.");
    return res.json();
  },

  deactivate: async (imageId: string): Promise<void> => {
    const res = await authFetch(`/tenants/homepage-images/${imageId}/deactivate/`, { method: "POST" });
    if (!res.ok) throw new Error("Could not remove this slide.");
  },

  reactivate: async (imageId: string): Promise<HomepageImage> => {
    const res = await authFetch(`/tenants/homepage-images/${imageId}/reactivate/`, { method: "POST" });
    if (!res.ok) throw new Error("Could not restore this slide.");
    return res.json();
  },

  delete: async (imageId: string): Promise<void> => {
    const res = await authFetch(`/tenants/homepage-images/${imageId}/`, { method: "DELETE" });
    if (!res.ok) throw new Error("Could not delete this slide.");
  },
};
