import { authFetch } from "./authFetch";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail?.toString() ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export interface LedgerWallet {
  id: string;
  scope: "general" | "own_family" | "town_elder";
  scope_display: string;
  family_id: string | null;
  family_name: string | null;
  balance: string;
  updated_at: string;
}

export interface LedgerWalletTransaction {
  id: string;
  kind: "credit" | "debit";
  amount: string;
  note: string;
  source_payment_receipt: string | null;
  actor_username: string | null;
  created_at: string;
}

/**
 * 'Each family should have their wallet being managed by the family
 * treasurer... the town leader should also have their wallet as
 * well... transparent since it's a transaction aspect.' A real, held
 * balance for the community, each family, and the Town Elders group —
 * see funerals.services.ledger_wallets_for for exactly who sees which.
 */
export const ledgerWalletsApi = {
  list: () => request<LedgerWallet[]>(`/ledger-wallets/`),
  transactions: (walletId: string) => request<LedgerWalletTransaction[]>(`/ledger-wallets/${walletId}/transactions/`),
  withdraw: (walletId: string, amount: string, note: string) =>
    request<LedgerWallet>(`/ledger-wallets/${walletId}/withdraw/`, {
      method: "POST",
      body: JSON.stringify({ amount, note }),
    }),
};
