"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { analyzePlan } from "@/lib/api";
import type { AnalyzeResponse } from "@/lib/types";

const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
  "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
  "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
  "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
  "DC",
] as const;

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

type Stage = "Processing PDF" | "Analyzing drawing" | "Generating estimate";

const STAGES: Stage[] = [
  "Processing PDF",
  "Analyzing drawing",
  "Generating estimate",
];

export default function AnalyzePage() {
  // Form state
  const [file, setFile] = useState<File | null>(null);
  const [projectName, setProjectName] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");

  // UI state
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<Stage>("Processing PDF");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── File handling ──────────────────────────────────────────────────────

  const validateFile = useCallback((f: File): string | null => {
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      return "Only PDF files are accepted.";
    }
    if (f.size > MAX_FILE_SIZE) {
      return "File exceeds 50 MB limit.";
    }
    return null;
  }, []);

  const handleFileSelect = useCallback(
    (f: File) => {
      const err = validateFile(f);
      if (err) {
        setError(err);
        return;
      }
      setError(null);
      setFile(f);
    },
    [validateFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f) handleFileSelect(f);
    },
    [handleFileSelect],
  );

  const onFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) handleFileSelect(f);
    },
    [handleFileSelect],
  );

  // ── Submit ─────────────────────────────────────────────────────────────

  const canSubmit = file && projectName.trim() && city.trim() && state;

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!file || !canSubmit) return;

      setLoading(true);
      setError(null);
      setResult(null);
      setStage("Processing PDF");

      // Simulate staged progress
      const t1 = setTimeout(() => setStage("Analyzing drawing"), 3000);
      const t2 = setTimeout(() => setStage("Generating estimate"), 12000);

      try {
        const data = await analyzePlan(file, {
          projectName: projectName.trim(),
          city: city.trim(),
          state,
        });
        setResult(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "An error occurred.");
      } finally {
        clearTimeout(t1);
        clearTimeout(t2);
        setLoading(false);
      }
    },
    [file, projectName, city, state, canSubmit],
  );

  const handleRetry = useCallback(() => {
    setError(null);
    setResult(null);
  }, []);

  // ── Helpers ────────────────────────────────────────────────────────────

  const fmt = (n: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      maximumFractionDigits: 0,
    }).format(n);

  const fmtSf = (n: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <main className="min-h-screen bg-[var(--color-navy-950)] text-white">
      <div className="mx-auto max-w-4xl px-6 py-16">
        {/* Header */}
        <div className="mb-10">
          <Link
            href="/"
            className="mb-6 inline-flex items-center gap-2 text-sm text-[var(--color-navy-400)] transition-colors hover:text-white"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path
                d="M13 7H1m0 0l5 5M1 7l5-5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Back to Home
          </Link>
          <h1 className="text-3xl font-bold tracking-tight">
            Analyze Floor Plan
          </h1>
          <p className="mt-2 text-[var(--color-navy-300)]">
            Upload a construction floor plan PDF to generate a conceptual budget
            estimate.
          </p>
        </div>

        {/* Upload Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Drag and drop zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`cursor-pointer rounded-lg border-2 border-dashed p-10 text-center transition-colors ${
              dragOver
                ? "border-[var(--color-blueprint-400)] bg-[var(--color-blueprint-500)]/5"
                : file
                  ? "border-[var(--color-blueprint-500)]/40 bg-[var(--color-navy-900)]"
                  : "border-[var(--color-navy-600)] bg-[var(--color-navy-900)]/50 hover:border-[var(--color-navy-400)]"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={onFileInputChange}
              className="hidden"
            />
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <svg
                  width="32"
                  height="32"
                  viewBox="0 0 24 24"
                  fill="none"
                  className="text-[var(--color-blueprint-400)]"
                >
                  <path
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <p className="text-sm font-medium text-white">{file.name}</p>
                <p className="text-xs text-[var(--color-navy-400)]">
                  {(file.size / 1024 / 1024).toFixed(1)} MB — Click or drop to
                  replace
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <svg
                  width="40"
                  height="40"
                  viewBox="0 0 24 24"
                  fill="none"
                  className="text-[var(--color-navy-400)]"
                >
                  <path
                    d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <div>
                  <p className="text-sm font-medium text-[var(--color-navy-200)]">
                    Drag and drop your PDF here, or click to browse
                  </p>
                  <p className="mt-1 text-xs text-[var(--color-navy-500)]">
                    PDF files only, up to 50 MB
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Form fields */}
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label
                htmlFor="projectName"
                className="mb-1.5 block text-sm font-medium text-[var(--color-navy-300)]"
              >
                Project Name
              </label>
              <input
                id="projectName"
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                placeholder="e.g. Main Street Office"
                className="w-full rounded-md border border-[var(--color-navy-700)] bg-[var(--color-navy-900)] px-3 py-2.5 text-sm text-white placeholder-[var(--color-navy-500)] transition-colors focus:border-[var(--color-blueprint-500)] focus:outline-none"
              />
            </div>
            <div>
              <label
                htmlFor="city"
                className="mb-1.5 block text-sm font-medium text-[var(--color-navy-300)]"
              >
                City
              </label>
              <input
                id="city"
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="e.g. Baltimore"
                className="w-full rounded-md border border-[var(--color-navy-700)] bg-[var(--color-navy-900)] px-3 py-2.5 text-sm text-white placeholder-[var(--color-navy-500)] transition-colors focus:border-[var(--color-blueprint-500)] focus:outline-none"
              />
            </div>
            <div>
              <label
                htmlFor="state"
                className="mb-1.5 block text-sm font-medium text-[var(--color-navy-300)]"
              >
                State
              </label>
              <select
                id="state"
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="w-full rounded-md border border-[var(--color-navy-700)] bg-[var(--color-navy-900)] px-3 py-2.5 text-sm text-white transition-colors focus:border-[var(--color-blueprint-500)] focus:outline-none"
              >
                <option value="">Select state</option>
                {US_STATES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={!canSubmit || loading}
            className="w-full rounded-md bg-[var(--color-accent-500)] px-6 py-3 text-sm font-bold tracking-wide text-white transition-all hover:bg-[var(--color-accent-400)] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-[var(--color-accent-500)] disabled:hover:shadow-none sm:w-auto"
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>
        </form>

        {/* Loading state */}
        {loading && (
          <div className="mt-10 rounded-lg border border-[var(--color-navy-700)] bg-[var(--color-navy-900)] p-8">
            <div className="flex flex-col items-center gap-6">
              {/* Spinner */}
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-navy-600)] border-t-[var(--color-blueprint-400)]" />
              <p className="text-sm font-medium text-white">{stage}...</p>
              {/* Stage indicators */}
              <div className="flex items-center gap-3">
                {STAGES.map((s, i) => {
                  const currentIdx = STAGES.indexOf(stage);
                  const done = i < currentIdx;
                  const active = i === currentIdx;
                  return (
                    <div key={s} className="flex items-center gap-3">
                      <div className="flex items-center gap-2">
                        <div
                          className={`h-2 w-2 rounded-full transition-colors ${
                            done
                              ? "bg-emerald-400"
                              : active
                                ? "bg-[var(--color-blueprint-400)]"
                                : "bg-[var(--color-navy-600)]"
                          }`}
                        />
                        <span
                          className={`text-xs ${
                            done
                              ? "text-emerald-400"
                              : active
                                ? "text-white"
                                : "text-[var(--color-navy-500)]"
                          }`}
                        >
                          {s}
                        </span>
                      </div>
                      {i < STAGES.length - 1 && (
                        <div className="h-px w-6 bg-[var(--color-navy-700)]" />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="mt-10 rounded-lg border border-red-500/30 bg-red-500/5 p-6">
            <div className="flex items-start gap-3">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                className="mt-0.5 shrink-0 text-red-400"
              >
                <path
                  d="M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              <div>
                <p className="text-sm font-medium text-red-300">{error}</p>
                <button
                  onClick={handleRetry}
                  className="mt-3 text-sm font-medium text-[var(--color-blueprint-400)] transition-colors hover:text-white"
                >
                  Try again
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {result && !loading && <ResultsView result={result} fmt={fmt} fmtSf={fmtSf} />}
      </div>
    </main>
  );
}

// ── Results component ──────────────────────────────────────────────────────

function ResultsView({
  result,
  fmt,
  fmtSf,
}: {
  result: AnalyzeResponse;
  fmt: (n: number) => string;
  fmtSf: (n: number) => string;
}) {
  const { estimate } = result;

  return (
    <section className="mt-12 space-y-6">
      {/* Header card */}
      <div className="rounded-lg border border-[var(--color-navy-700)] bg-[var(--color-navy-900)] p-6">
        <div className="mb-4 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold">{estimate.project_name}</h2>
            <p className="mt-1 text-sm text-[var(--color-navy-400)]">
              {estimate.building_summary.building_type} &middot;{" "}
              {estimate.building_summary.gross_sf.toLocaleString()} SF &middot;{" "}
              {estimate.building_summary.stories} stories &middot;{" "}
              {estimate.building_summary.structural_system} &middot;{" "}
              {estimate.building_summary.location}
            </p>
          </div>
        </div>
        {/* Total cost */}
        <div className="flex flex-wrap items-end gap-8">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-navy-400)]">
              Total Estimated Cost
            </p>
            <p className="font-mono text-3xl font-bold text-white">
              {fmt(estimate.total_cost.expected)}
            </p>
            <p className="mt-1 text-xs text-[var(--color-navy-500)]">
              Range: {fmt(estimate.total_cost.low)} &ndash;{" "}
              {fmt(estimate.total_cost.high)}
            </p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-[var(--color-navy-400)]">
              Cost per SF
            </p>
            <p className="font-mono text-xl font-bold text-[var(--color-blueprint-300)]">
              {fmtSf(estimate.cost_per_sf.expected)}
            </p>
            <p className="mt-1 text-xs text-[var(--color-navy-500)]">
              Range: {fmtSf(estimate.cost_per_sf.low)} &ndash;{" "}
              {fmtSf(estimate.cost_per_sf.high)}
            </p>
          </div>
        </div>
      </div>

      {/* Division breakdown */}
      <div className="rounded-lg border border-[var(--color-navy-700)] bg-[var(--color-navy-900)] p-6">
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-[var(--color-navy-300)]">
          Division Breakdown
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-navy-700)]">
                <th className="pb-2 pr-4 font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                  Div
                </th>
                <th className="pb-2 pr-4 font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                  Name
                </th>
                <th className="pb-2 pr-4 text-right font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                  Expected
                </th>
                <th className="pb-2 pr-4 text-right font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                  %
                </th>
                <th className="pb-2 text-right font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                  Range
                </th>
              </tr>
            </thead>
            <tbody>
              {[...estimate.breakdown]
                .sort((a, b) => b.cost.expected - a.cost.expected)
                .map((div, i) => (
                  <tr
                    key={div.csi_division}
                    className={`border-b border-[var(--color-navy-700)]/50 ${
                      i < 3 ? "bg-[var(--color-blueprint-500)]/3" : ""
                    }`}
                  >
                    <td className="py-2.5 pr-4 font-mono text-[var(--color-navy-400)]">
                      {div.csi_division}
                    </td>
                    <td className="py-2.5 pr-4 text-[var(--color-navy-200)]">
                      {div.division_name}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-white">
                      {fmt(div.cost.expected)}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-mono text-[var(--color-navy-400)]">
                      {div.percent_of_total.toFixed(1)}%
                    </td>
                    <td className="py-2.5 text-right font-mono text-xs text-[var(--color-navy-500)]">
                      {fmt(div.cost.low)} &ndash; {fmt(div.cost.high)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Assumptions */}
      <DisclosurePanel title="Assumptions">
        <div className="space-y-3">
          {estimate.assumptions.map((a) => (
            <div
              key={a.parameter}
              className="flex items-start justify-between gap-4 rounded border border-[var(--color-navy-700)]/50 px-4 py-3"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-[var(--color-navy-200)]">
                  {a.parameter}
                </p>
                <p className="text-sm text-[var(--color-navy-400)]">
                  {a.assumed_value}
                </p>
                <p className="mt-1 text-xs text-[var(--color-navy-500)]">
                  {a.reasoning}
                </p>
              </div>
              <ConfidenceBadge confidence={a.confidence} />
            </div>
          ))}
        </div>
      </DisclosurePanel>

      {/* AI Reasoning */}
      {result.analysis.reasoning && (
        <DisclosurePanel title="AI Reasoning">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--color-navy-300)]">
            {result.analysis.reasoning}
          </p>
          {result.analysis.warnings.length > 0 && (
            <div className="mt-4 space-y-1">
              <p className="text-xs font-semibold uppercase tracking-wider text-yellow-400">
                Warnings
              </p>
              {result.analysis.warnings.map((w, i) => (
                <p key={i} className="text-sm text-yellow-300/80">
                  {w}
                </p>
              ))}
            </div>
          )}
        </DisclosurePanel>
      )}

      {/* Metadata footer */}
      <div className="flex flex-wrap gap-6 border-t border-[var(--color-navy-800)] pt-4 text-xs text-[var(--color-navy-500)]">
        <span>Generated: {new Date(estimate.generated_at).toLocaleString()}</span>
        <span>Engine: {estimate.metadata.engine_version}</span>
        <span>Method: {estimate.metadata.estimation_method}</span>
        <span>Location Factor: {estimate.location_factor.toFixed(2)}</span>
      </div>
    </section>
  );
}

// ── Shared UI components ───────────────────────────────────────────────────

function DisclosurePanel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-lg border border-[var(--color-navy-700)] bg-[var(--color-navy-900)]">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-6 py-4 text-left"
      >
        <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-navy-300)]">
          {title}
        </h3>
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          className={`text-[var(--color-navy-500)] transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path
            d="M4 6l4 4 4-4"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open && <div className="px-6 pb-6">{children}</div>}
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const colors: Record<string, string> = {
    high: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
    medium: "border-yellow-500/30 bg-yellow-500/10 text-yellow-400",
    low: "border-red-500/30 bg-red-500/10 text-red-400",
  };
  const cls = colors[confidence] ?? colors.low;

  return (
    <span
      className={`shrink-0 rounded border px-2 py-0.5 font-mono text-[10px] font-medium uppercase ${cls}`}
    >
      {confidence}
    </span>
  );
}
