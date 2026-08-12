"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  label: string;
}

interface State {
  hasError: boolean;
  message: string;
}

/**
 * A genuine safety net: if anything inside throws during render, this
 * catches it and shows a small, recoverable message instead of the
 * whole page going down with Next.js's generic "Application error: a
 * client-side exception has occurred" screen. `label` gets logged to
 * the console so a real stack trace is still easy to find, even
 * though the person using the app just sees a quiet fallback.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // eslint-disable-next-line no-console
    console.error(`[${this.props.label}] crashed:`, error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <p className="p-3 text-xs text-[var(--clay-red,#a93b2e)]">
            {this.props.label} couldn&apos;t load. The rest of the page is unaffected.
          </p>
        )
      );
    }
    return this.props.children;
  }
}
