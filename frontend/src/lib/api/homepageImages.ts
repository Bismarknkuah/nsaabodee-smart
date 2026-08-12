const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
import { authFetch } from "./authFetch";

export interface HomepageImage {
  id: string;
  image_url: string | null;
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

  upload: async (input: { image: File; caption?: string; subcaption?: string; display_order?: number }): Promise<HomepageImage> => {
    const form = new FormData();
    form.set("image", input.image);
    if (input.caption) form.set("caption", input.caption);
    if (input.subcaption) form.set("subcaption", input.subcaption);
    if (input.display_order !== undefined) form.set("display_order", String(input.display_order));
    const res = await authFetch("/tenants/homepage-images/manage/", { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? "Could not upload this image.");
    }
    return res.json();
  },

  deactivate: async (imageId: string): Promise<void> => {
    const res = await authFetch(`/tenants/homepage-images/${imageId}/deactivate/`, { method: "POST" });
    if (!res.ok) throw new Error("Could not remove this image.");
  },
};
