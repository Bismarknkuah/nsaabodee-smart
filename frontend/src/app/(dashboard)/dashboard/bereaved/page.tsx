"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";

interface BereavedFuneral {
  funeral_id: string;
  deceased_name: string;
  overview: { net_cash_position: string };
}

/** Deliberately the quietest page in the whole app — a formal statement, not a dashboard. No tiles, no charts, no color-coded urgency; just what's true, plainly stated. */
export default function BereavedDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const funerals = (data?.sections.bereaved_funerals as BereavedFuneral[] | undefined) ?? [];

  return (
    <DashboardPageShell folio="Folio VIII" register="Bereavement Statement" title="Your Family's Funeral" subtitle="A plain account of where things stand — for the family you represent.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {data && (
        <div className="lg:col-span-2 mx-auto w-full max-w-xl border border-[var(--rule)] bg-white p-8">
          {funerals.length === 0 ? (
            <p className="text-center text-sm text-[var(--ink-soft)]">There is no active funeral for your family right now.</p>
          ) : (
            <div className="divide-y divide-[var(--rule)]">
              {funerals.map((f) => (
                <div key={f.funeral_id} className="py-5 first:pt-0 last:pb-0">
                  <p className="font-display text-xl">
                    <Link href={`/funerals/${f.funeral_id}`} className="hover:text-[var(--forest)] hover:underline">
                      {f.deceased_name}
                    </Link>
                  </p>
                  <p className="mt-2 text-sm text-[var(--ink-soft)]">
                    Net position: <span className="font-mono text-[var(--ink)]">{formatCedis(f.overview.net_cash_position)}</span>
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </DashboardPageShell>
  );
}
