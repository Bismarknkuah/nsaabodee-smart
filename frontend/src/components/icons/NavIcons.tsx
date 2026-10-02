/**
 * A small, hand-built icon set — consistent 20×20 stroke style, no
 * external icon library dependency. Enough for the sidebar nav and
 * account section; not meant to be a general-purpose icon system.
 */
import type { SVGProps } from "react";

function base(props: SVGProps<SVGSVGElement>) {
  return {
    width: 18,
    height: 18,
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...props,
  };
}

export const IconDashboard = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="2.5" y="2.5" width="6.5" height="6.5" rx="1" /><rect x="11" y="2.5" width="6.5" height="6.5" rx="1" /><rect x="2.5" y="11" width="6.5" height="6.5" rx="1" /><rect x="11" y="11" width="6.5" height="6.5" rx="1" /></svg>
);
export const IconCommunities = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><circle cx="7" cy="6.5" r="2.3" /><circle cx="14" cy="6.5" r="2.3" /><path d="M2.5 17c0-2.8 2-4.5 4.5-4.5s4.5 1.7 4.5 4.5M10.5 17c0-2.8 2-4.5 4.5-4.5s4.5 1.7 4.5 4.5" /></svg>
);
export const IconFamilies = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M10 2.5l7 4v7l-7 4-7-4v-7z" /><circle cx="10" cy="9.5" r="2" /></svg>
);
export const IconFunerals = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M10 2.5v6M6 8.5h8l1.5 9h-11z" /><path d="M4 17.5h12" /></svg>
);
export const IconDesk = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="2.5" y="9" width="15" height="7.5" rx="1" /><path d="M5 9V5.5a2 2 0 012-2h6a2 2 0 012 2V9" /></svg>
);
export const IconSync = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M16.5 8.5A6.5 6.5 0 005 5.6M3.5 4v3h3M3.5 11.5A6.5 6.5 0 0015 14.4M16.5 16v-3h-3" /></svg>
);
export const IconMembers = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><circle cx="10" cy="6.5" r="3" /><path d="M3.5 17c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6" /></svg>
);
export const IconTasks = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="3" y="3" width="14" height="14" rx="1.5" /><path d="M6.5 10.2l2 2 5-5" /></svg>
);
export const IconRules = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M10 2.5l6 2.3v5c0 4-2.6 7-6 7.7-3.4-.7-6-3.7-6-7.7v-5z" /><path d="M7.3 10l2 2 3.4-3.6" /></svg>
);
export const IconReports = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="3.5" y="2.5" width="13" height="15" rx="1" /><path d="M7 7h6M7 10.5h6M7 14h3.5" /></svg>
);
export const IconReceipt = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M5 2.5h10v15l-2.2-1.5L10.5 17l-2.3-1-2.3 1-1-1z" /><path d="M7.2 6.5h5.6M7.2 9.7h5.6" /></svg>
);
export const IconGift = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="3" y="8" width="14" height="9" rx="1" /><path d="M3 11.5h14M10 8v9" /><path d="M10 8C8 8 6.5 6.8 6.5 5.3 6.5 4 7.5 3 8.8 3c1.4 0 1.9 1.4 1.2 2.7M10 8c2 0 3.5-1.2 3.5-2.7C13.5 4 12.5 3 11.2 3 9.8 3 9.3 4.4 10 5.7" /></svg>
);
export const IconBell = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M10 2.8c-2.5 0-4 1.9-4 4.4v2.6L4.5 12.8h11L14 9.8V7.2c0-2.5-1.5-4.4-4-4.4z" /><path d="M8.3 15.5a1.8 1.8 0 003.4 0" /></svg>
);
export const IconInactive = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><circle cx="10" cy="10" r="7.2" /><path d="M7 7l6 6M13 7l-6 6" /></svg>
);
export const IconAlert = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M10 3l7.5 13H2.5z" /><path d="M10 8.3v3.2" /><circle cx="10" cy="14" r="0.15" fill="currentColor" /></svg>
);
export const IconMeeting = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M4 4h9l3.5 3.5V16H4z" /><path d="M7 8.5h6M7 11.5h6" /></svg>
);
export const IconUser = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><circle cx="10" cy="7" r="3" /><path d="M4 17c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5" /></svg>
);
export const IconSignOut = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M8 3H4.5v14H8" /><path d="M8.5 10H17M14 6.5l3.5 3.5-3.5 3.5" /></svg>
);
export const IconMenu = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M2.5 5.5h15M2.5 10h15M2.5 14.5h15" /></svg>
);
export const IconClose = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M4.5 4.5l11 11M15.5 4.5l-11 11" /></svg>
);
