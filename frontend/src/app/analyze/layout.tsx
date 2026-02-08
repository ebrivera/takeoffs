import { AnalyzeErrorBoundary } from "./error-boundary";

export default function AnalyzeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AnalyzeErrorBoundary>{children}</AnalyzeErrorBoundary>;
}
