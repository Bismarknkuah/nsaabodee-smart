const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface MemorialTribute {
  author_name: string;
  message: string;
  created_at: string;
}

export interface MemorialPayoutAccount {
  account_type: "mobile_money" | "bank";
  provider_name: string;
  account_number: string;
  account_holder_name: string;
}

export interface MemorialPageData {
  funeral_id: string;
  deceased_name: string;
  date_of_death: string | null;
  funeral_date: string | null;
  tribute_message: string;
  photo_url: string | null;
  tributes: MemorialTribute[];
  contribution_total?: string;
  payout_accounts: MemorialPayoutAccount[];
}

/**
 * "A dignified public page for the funeral... a lasting place to
 * remember your loved one." Deliberately plain fetch(), not authFetch —
 * this page has to work for someone with no account and no login at
 * all, the same way viewing it on the backend needs no authentication
 * either.
 */
export const memorialApi = {
  get: async (funeralId: string): Promise<MemorialPageData | null> => {
    const res = await fetch(`${BASE}/api/funerals/${funeralId}/memorial/`);
    if (res.status === 404) return null;
    if (!res.ok) throw new Error("Could not load this memorial page.");
    return res.json();
  },

  submitTribute: async (funeralId: string, authorName: string, message: string): Promise<void> => {
    const res = await fetch(`${BASE}/api/funerals/${funeralId}/memorial/tributes/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ author_name: authorName, message }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? body.author_name?.[0] ?? body.message?.[0] ?? "Could not submit your tribute.");
    }
  },
};
