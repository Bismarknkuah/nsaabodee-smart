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
  community_registration_desk: "/dashboard/registration",
  treasurer: "/dashboard/financial",
  financial_secretary: "/dashboard/financial",
  auditor: "/dashboard/financial",
  collector: "/dashboard/collector",
  // 'All executive personal dashboard is the same as the community
  // member dashboard since they are members.' Arrears Collector shares
  // Collector's own dashboard rather than falling through to the
  // default — it is the same "your own cash position, and who you
  // can collect from" concept, just scoped to arrears instead of
  // active-funeral obligations.
  arrears_collector: "/dashboard/arrears",
  family_head: "/dashboard/family",
  family_secretary: "/dashboard/family",
  family_treasurer: "/dashboard/family",
  // 'We have a family arrears collector who is responsible for
  // managing and collecting his family arrears only.' Its own page,
  // not the Family Head's oversight dashboard — collecting is this
  // role's actual job, the same underlying concept as
  // arrears_collector above, just scoped to one family.
  family_arrears_officer: "/dashboard/family-arrears",
  family_registration_officer: "/dashboard/registration",
  // Town-Elders-scoped executives share the Traditional Leader's own
  // dashboard, the Town Elders group's equivalent of the above.
  town_registration_officer: "/dashboard/registration",
  town_elders_arrears_officer: "/dashboard/chief",
  community_member: "/dashboard/member",
  notification_officer: "/dashboard/notification-officer",
  bereaved_rep: "/dashboard/bereaved",
  guest: "/dashboard/guest",
  platform_admin: "/dashboard/platform",
};

export function dashboardRouteForRole(role: string | undefined | null): string {
  return (role && DASHBOARD_ROUTE_BY_ROLE[role]) || "/dashboard/community";
}
