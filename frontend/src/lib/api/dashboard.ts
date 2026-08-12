import { authFetch } from "./authFetch";

export interface DashboardResponse {
  role: string;
  sections: Record<string, unknown>;
}

export const dashboardApi = {
  get: async (): Promise<DashboardResponse> => {
    const res = await authFetch("/dashboard/");
    if (!res.ok) throw new Error(`Could not load dashboard (${res.status})`);
    return res.json();
  },
};
