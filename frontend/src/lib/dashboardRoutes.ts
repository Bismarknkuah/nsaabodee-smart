/**
 * "Can each user type have their own separate or own dashboard pages,
 * so that editing it wouldn't be a problem?" Each role now gets its
 * own real route and file — editing one can never accidentally break
 * another, and each is free to grow features unique to that role
 * without competing for space in one shared component tree.
 */
export const DASHBOARD_ROUTE_BY_ROLE: Record<string, string> = {
  traditional_leader: "/dashboard/chief",
  community_admin: "/dashboard/community",
  chairman: "/dashboard/community",
  secretary: "/dashboard/community",
  treasurer: "/dashboard/financial",
  financial_secretary: "/dashboard/financial",
  auditor: "/dashboard/financial",
  collector: "/dashboard/collector",
  family_head: "/dashboard/family",
  family_secretary: "/dashboard/family",
  family_treasurer: "/dashboard/family",
  community_member: "/dashboard/member",
  notification_officer: "/dashboard/notification-officer",
  bereaved_rep: "/dashboard/bereaved",
  guest: "/dashboard/guest",
  platform_admin: "/dashboard/platform",
};

export function dashboardRouteForRole(role: string | undefined | null): string {
  return (role && DASHBOARD_ROUTE_BY_ROLE[role]) || "/dashboard/community";
}
