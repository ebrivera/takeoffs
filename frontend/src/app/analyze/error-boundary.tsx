"use client";

import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class AnalyzeErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error("AnalyzeErrorBoundary caught:", error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-[var(--color-navy-950)] px-6">
          <div className="max-w-md rounded-lg border border-red-500/30 bg-red-500/5 p-8 text-center">
            <h2 className="text-lg font-bold text-white">
              Something went wrong
            </h2>
            <p className="mt-2 text-sm text-[var(--color-navy-400)]">
              An unexpected error occurred. Please try again.
            </p>
            <button
              onClick={() => this.setState({ hasError: false })}
              className="mt-4 rounded-md bg-[var(--color-blueprint-500)] px-5 py-2.5 text-sm font-bold text-white transition-all hover:bg-[var(--color-blueprint-400)]"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
