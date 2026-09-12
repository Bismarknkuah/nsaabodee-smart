"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useAuthStore } from "@/store/authStore";

/**
 * 'The family executives should have the expenses button or feature
 * on the multi task bar.' Family expense management already exists
 * (see the Family Fund page's Funeral Expenses panel), but it lives
 * behind a dynamic /family-fund/{familyId} URL a nav link can't point
 * to directly without knowing which family in advance. This page is
 * that missing, stable entry point: resolves the signed-in officer's
 * own family (the same linked_member_id detection used everywhere
 * else in this platform) and lands them straight on it — never
 * exposing a family picker, since Family Head/Secretary/Treasurer
 * should never see another family's own fund at all.
 */
export default function MyFamilyExpensesPage() {
  const router = useRouter();
  const currentUser = useAuthStore((s) => s.user);
  const { data: families, isLoading } = useFamilies(false);

  const ownFamily = families?.find(
    (f) =>
      f.family_head?.id === currentUser?.linked_member_id ||
      f.family_secretary?.id === currentUser?.linked_member_id ||
      f.family_treasurer?.id === currentUser?.linked_member_id
  );

  useEffect(() => {
    if (ownFamily) {
      router.replace(`/family-fund/${ownFamily.id}`);
    }
  }, [ownFamily, router]);

  return (
    <div className="font-body flex min-h-screen items-center justify-center bg-[var(--paper)] text-[var(--ink)]">
      {isLoading || ownFamily ? (
        <p className="text-sm text-[var(--ink-soft)]">Opening your family&apos;s expenses…</p>
      ) : (
        <p className="text-sm text-[var(--clay-red)]">
          You&apos;re not currently recognized as an officer of any family — contact your Community Admin.
        </p>
      )}
    </div>
  );
}
