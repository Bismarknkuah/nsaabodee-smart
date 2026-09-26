import type { SVGProps } from "react";

function base(props: SVGProps<SVGSVGElement>) {
  return {
    width: 16, height: 16, viewBox: "0 0 20 20", fill: "none",
    stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
    ...props,
  };
}

export const IconMoney = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><rect x="2.5" y="5" width="15" height="10" rx="2" /><circle cx="10" cy="10" r="2.3" /></svg>
);
export const IconPeople = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><circle cx="10" cy="6.5" r="3" /><path d="M3.5 17c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6" /></svg>
);
export const IconWarning = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M10 3l7.5 13H2.5z" /><path d="M10 8.3v3.2" /><circle cx="10" cy="14" r="0.15" fill="currentColor" /></svg>
);
export const IconFuneral = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M10 2.5v6M6 8.5h8l1.5 9h-11z" /></svg>
);
export const IconHome = (p: SVGProps<SVGSVGElement>) => (
  <svg {...base(p)}><path d="M3 9.5L10 3l7 6.5" /><path d="M5 8.5V17h10V8.5" /></svg>
);
