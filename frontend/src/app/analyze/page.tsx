"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { analyzePlan, estimateFromModel, getSampleEstimate } from "@/lib/api";
import type {
  AnalyzeResponse,
  BuildingModel,
  CostEstimate,
  Confidence,
  SpaceCost,
  SpaceProgramPayload,
  SpacePayload,
} from "@/lib/types";
import {
  BuildingType,
  RoomType,
  StructuralSystem,
  ExteriorWall,
} from "@/lib/types";

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

// Human-readable labels for enum values
const BUILDING_TYPE_LABELS: Record<string, string> = {
  [BuildingType.APARTMENT_LOW_RISE]: "Apartment (Low Rise)",
  [BuildingType.APARTMENT_MID_RISE]: "Apartment (Mid Rise)",
  [BuildingType.APARTMENT_HIGH_RISE]: "Apartment (High Rise)",
  [BuildingType.OFFICE_LOW_RISE]: "Office (Low Rise)",
  [BuildingType.OFFICE_MID_RISE]: "Office (Mid Rise)",
  [BuildingType.OFFICE_HIGH_RISE]: "Office (High Rise)",
  [BuildingType.RETAIL]: "Retail",
  [BuildingType.WAREHOUSE]: "Warehouse",
  [BuildingType.SCHOOL_ELEMENTARY]: "School (Elementary)",
  [BuildingType.SCHOOL_HIGH]: "School (High)",
  [BuildingType.HOSPITAL]: "Hospital",
  [BuildingType.HOTEL]: "Hotel",
};

const STRUCTURAL_LABELS: Record<string, string> = {
  [StructuralSystem.WOOD_FRAME]: "Wood Frame",
  [StructuralSystem.STEEL_FRAME]: "Steel Frame",
  [StructuralSystem.CONCRETE_FRAME]: "Concrete Frame",
  [StructuralSystem.MASONRY_BEARING]: "Masonry Bearing",
  [StructuralSystem.PRECAST_CONCRETE]: "Precast Concrete",
};

const EXTERIOR_LABELS: Record<string, string> = {
  [ExteriorWall.BRICK_VENEER]: "Brick Veneer",
  [ExteriorWall.CURTAIN_WALL]: "Curtain Wall",
  [ExteriorWall.METAL_PANEL]: "Metal Panel",
  [ExteriorWall.PRECAST_PANEL]: "Precast Panel",
  [ExteriorWall.STUCCO]: "Stucco",
  [ExteriorWall.WOOD_SIDING]: "Wood Siding",
  [ExteriorWall.EIFS]: "EIFS",
};

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

  const [loadingSample, setLoadingSample] = useState(false);

  const handleSample = useCallback(async () => {
    setLoadingSample(true);
    setError(null);
    setResult(null);
    try {
      const data = await getSampleEstimate();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sample.");
    } finally {
      setLoadingSample(false);
    }
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

          {/* Submit buttons */}
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              disabled={!canSubmit || loading || loadingSample}
              className="w-full rounded-md bg-[var(--color-accent-500)] px-6 py-3 text-sm font-bold tracking-wide text-white transition-all hover:bg-[var(--color-accent-400)] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-[var(--color-accent-500)] disabled:hover:shadow-none sm:w-auto"
            >
              {loading ? "Analyzing..." : "Analyze"}
            </button>
            <button
              type="button"
              disabled={loading || loadingSample}
              onClick={handleSample}
              className="w-full rounded-md border border-[var(--color-navy-600)] px-6 py-3 text-sm font-medium text-[var(--color-navy-300)] transition-all hover:border-[var(--color-navy-400)] hover:text-white disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
            >
              {loadingSample ? "Loading..." : "Try sample estimate"}
            </button>
          </div>
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
  const originalEstimate = result.estimate;

  // Editable building model state
  const [editedModel, setEditedModel] = useState<BuildingModel>(
    () => structuredClone(result.building_model),
  );
  const [adjustedEstimate, setAdjustedEstimate] = useState<CostEstimate | null>(null);
  const [showingAdjusted, setShowingAdjusted] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [recalcError, setRecalcError] = useState<string | null>(null);

  // Track if model has been edited
  const hasChanges = JSON.stringify(editedModel) !== JSON.stringify(result.building_model);

  const estimate = showingAdjusted && adjustedEstimate ? adjustedEstimate : originalEstimate;

  // Space breakdown: prefer estimate-level, fall back to top-level analyze response
  const spaceBreakdown: SpaceCost[] | null =
    estimate.space_breakdown ?? result.space_breakdown ?? null;

  const handleRecalculate = useCallback(async () => {
    setRecalculating(true);
    setRecalcError(null);
    try {
      const newEstimate = await estimateFromModel(editedModel);
      setAdjustedEstimate(newEstimate);
      setShowingAdjusted(true);
    } catch (err) {
      setRecalcError(err instanceof Error ? err.message : "Recalculation failed.");
    } finally {
      setRecalculating(false);
    }
  }, [editedModel]);

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
          {/* Toggle between AI and adjusted */}
          {adjustedEstimate && (
            <div className="flex gap-1 rounded-md border border-[var(--color-navy-700)] bg-[var(--color-navy-800)] p-0.5">
              <button
                type="button"
                onClick={() => setShowingAdjusted(false)}
                className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                  !showingAdjusted
                    ? "bg-[var(--color-navy-600)] text-white"
                    : "text-[var(--color-navy-400)] hover:text-white"
                }`}
              >
                AI Estimate
              </button>
              <button
                type="button"
                onClick={() => setShowingAdjusted(true)}
                className={`rounded px-3 py-1 text-xs font-medium transition-colors ${
                  showingAdjusted
                    ? "bg-[var(--color-blueprint-500)] text-white"
                    : "text-[var(--color-navy-400)] hover:text-white"
                }`}
              >
                Adjusted
              </button>
            </div>
          )}
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

      {/* Building Parameters (editable) */}
      <BuildingParametersEditor
        model={editedModel}
        confidence={result.building_model.confidence}
        onChange={setEditedModel}
        hasChanges={hasChanges}
        recalculating={recalculating}
        recalcError={recalcError}
        onRecalculate={handleRecalculate}
      />

      {/* Space Program */}
      <SpaceProgramSection
        spaceBreakdown={spaceBreakdown}
        roomDetectionMethod={result.room_detection_method}
        buildingModel={editedModel}
        onRecalculated={(newEstimate) => {
          setAdjustedEstimate(newEstimate);
          setShowingAdjusted(true);
        }}
        fmt={fmt}
        fmtSf={fmtSf}
      />

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

// ── Source indicator icons ──────────────────────────────────────────────────

const SOURCE_META: Record<string, { label: string; tip: string }> = {
  geometry: { label: "Measured", tip: "Detected from floor plan geometry" },
  llm: { label: "AI", tip: "Interpreted by AI model" },
  assumed: { label: "Assumed", tip: "Default distribution based on building type" },
  user_override: { label: "Edited", tip: "Modified by user" },
};

function SourceIcon({ source }: { source: string }) {
  const meta = SOURCE_META[source] ?? SOURCE_META.assumed;

  const icon = (() => {
    switch (source) {
      // Tape measure — geometry/measured
      case "geometry":
        return (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <rect x="1" y="4" width="14" height="8" rx="1" stroke="currentColor" strokeWidth="1.2" />
            <line x1="4" y1="4" x2="4" y2="7" stroke="currentColor" strokeWidth="1" />
            <line x1="7" y1="4" x2="7" y2="8" stroke="currentColor" strokeWidth="1" />
            <line x1="10" y1="4" x2="10" y2="7" stroke="currentColor" strokeWidth="1" />
            <line x1="13" y1="4" x2="13" y2="7" stroke="currentColor" strokeWidth="1" />
          </svg>
        );
      // Brain — LLM
      case "llm":
        return (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path
              d="M5 13V11C3.34 11 2 9.66 2 8s1.34-3 3-3V3.5C5 2.67 5.67 2 6.5 2S8 2.67 8 3.5V5c1.66 0 3 1.34 3 3s-1.34 3-3 3v2"
              stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"
            />
            <path
              d="M11 8c1.1 0 2-.9 2-2s-.9-2-2-2"
              stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"
            />
            <circle cx="6" cy="8" r="1" fill="currentColor" />
          </svg>
        );
      // Dashed circle — assumed
      case "assumed":
        return (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.2" strokeDasharray="3 2" />
          </svg>
        );
      // Pencil — user override
      case "user_override":
        return (
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path
              d="M11.5 2.5l2 2L5 13H3v-2l8.5-8.5z"
              stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"
            />
          </svg>
        );
      default:
        return null;
    }
  })();

  return (
    <span className="group relative inline-flex items-center text-[var(--color-navy-400)]" title={meta.tip}>
      {icon}
    </span>
  );
}

// Human-readable room type labels
const ROOM_TYPE_LABELS: Record<string, string> = {
  living_room: "Living Room",
  kitchen: "Kitchen",
  dining: "Dining",
  bedroom: "Bedroom",
  bathroom: "Bathroom",
  restroom: "Restroom",
  wc: "WC",
  utility: "Utility",
  laundry: "Laundry",
  closet: "Closet",
  porch: "Porch",
  lobby: "Lobby",
  open_office: "Open Office",
  private_office: "Private Office",
  conference: "Conference",
  corridor: "Corridor",
  kitchen_break: "Kitchen/Break",
  mechanical_room: "Mechanical",
  storage: "Storage",
  retail_sales: "Retail Sales",
  classroom: "Classroom",
  lab: "Lab",
  patient_room: "Patient Room",
  operating_room: "Operating Room",
  warehouse_storage: "Warehouse",
  loading_dock: "Loading Dock",
  common_area: "Common Area",
  stairwell_elevator: "Stairwell/Elevator",
  parking: "Parking",
  garage: "Garage",
  entry: "Entry",
  foyer: "Foyer",
  hallway: "Hallway",
  other: "Other",
};

function formatRoomType(roomType: string): string {
  return ROOM_TYPE_LABELS[roomType] ?? roomType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Editable room row type ──────────────────────────────────────────────────

interface EditableRoom {
  name: string;
  room_type: string;
  area_sf: number;
  source: string;
  confidence: string;
}

function spaceCostToEditable(space: SpaceCost): EditableRoom {
  return {
    name: space.name,
    room_type: space.room_type,
    area_sf: space.area_sf,
    source: space.source,
    confidence: space.source === "geometry" ? "high" : space.source === "llm" ? "medium" : "low",
  };
}

function editableToPayload(room: EditableRoom): SpacePayload {
  return {
    room_type: room.room_type,
    name: room.name,
    area_sf: room.area_sf,
    count: 1,
    source: room.source,
    confidence: room.confidence,
  };
}

// ── Space Program Section ──────────────────────────────────────────────────

function SpaceProgramSection({
  spaceBreakdown,
  roomDetectionMethod,
  buildingModel,
  onRecalculated,
  fmt,
  fmtSf,
}: {
  spaceBreakdown: SpaceCost[] | null;
  roomDetectionMethod?: string;
  buildingModel: BuildingModel;
  onRecalculated: (estimate: CostEstimate) => void;
  fmt: (n: number) => string;
  fmtSf: (n: number) => string;
}) {
  const methodLabel =
    roomDetectionMethod === "polygonize"
      ? "Geometry-detected rooms"
      : roomDetectionMethod === "llm_only"
        ? "AI-interpreted rooms"
        : "Assumed distribution";

  // Editable room state — initialized from spaceBreakdown
  const [editableRooms, setEditableRooms] = useState<EditableRoom[]>(() =>
    spaceBreakdown ? spaceBreakdown.map(spaceCostToEditable) : [],
  );
  const [hasEdits, setHasEdits] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [recalcError, setRecalcError] = useState<string | null>(null);

  const inputCls =
    "w-full rounded border border-[var(--color-navy-700)] bg-[var(--color-navy-800)] px-2 py-1.5 text-sm text-white transition-colors focus:border-[var(--color-blueprint-500)] focus:outline-none";

  const updateRoom = (index: number, patch: Partial<EditableRoom>) => {
    setEditableRooms((prev) =>
      prev.map((r, i) =>
        i === index ? { ...r, ...patch, source: "user_override" } : r,
      ),
    );
    setHasEdits(true);
  };

  const addRoom = () => {
    setEditableRooms((prev) => [
      ...prev,
      {
        name: "",
        room_type: RoomType.OTHER,
        area_sf: 0,
        source: "user_override",
        confidence: "low",
      },
    ]);
    setHasEdits(true);
  };

  const removeRoom = (index: number) => {
    setEditableRooms((prev) => prev.filter((_, i) => i !== index));
    setHasEdits(true);
  };

  const handleRecalculate = async () => {
    setRecalculating(true);
    setRecalcError(null);
    try {
      const spaceProgram: SpaceProgramPayload = {
        spaces: editableRooms.map(editableToPayload),
        building_type: buildingModel.building_type,
      };
      const newEstimate = await estimateFromModel(buildingModel, spaceProgram);
      onRecalculated(newEstimate);
      // Update editable rooms from new breakdown
      if (newEstimate.space_breakdown) {
        setEditableRooms(newEstimate.space_breakdown.map(spaceCostToEditable));
      }
      setHasEdits(false);
    } catch (err) {
      setRecalcError(err instanceof Error ? err.message : "Recalculation failed.");
    } finally {
      setRecalculating(false);
    }
  };

  return (
    <div className="rounded-lg border border-[var(--color-navy-700)] bg-[var(--color-navy-900)] p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-[var(--color-navy-300)]">
          Space Program
        </h3>
        {roomDetectionMethod && (
          <span className="rounded border border-[var(--color-navy-700)] bg-[var(--color-navy-800)] px-2 py-0.5 text-[10px] font-medium text-[var(--color-navy-400)]">
            {methodLabel}
          </span>
        )}
      </div>

      {spaceBreakdown && spaceBreakdown.length > 0 ? (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-navy-700)]">
                  <th className="pb-2 pr-4 font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                    Room
                  </th>
                  <th className="pb-2 pr-4 font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                    Type
                  </th>
                  <th className="pb-2 pr-4 text-right font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                    Area (SF)
                  </th>
                  <th className="pb-2 pr-4 text-right font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                    $/SF
                  </th>
                  <th className="pb-2 pr-4 text-right font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                    Total
                  </th>
                  <th className="pb-2 pr-4 text-right font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                    %
                  </th>
                  <th className="pb-2 text-center font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                    Src
                  </th>
                  <th className="pb-2 text-center font-mono text-xs font-medium uppercase tracking-wider text-[var(--color-navy-500)]">
                  </th>
                </tr>
              </thead>
              <tbody>
                {editableRooms.map((room, i) => {
                  // Find matching cost data from the original breakdown
                  const costData = spaceBreakdown[i] as SpaceCost | undefined;
                  return (
                    <tr
                      key={i}
                      className="border-b border-[var(--color-navy-700)]/50"
                    >
                      <td className="py-2 pr-4">
                        <input
                          type="text"
                          value={room.name}
                          onChange={(e) => updateRoom(i, { name: e.target.value })}
                          className={inputCls}
                          style={{ minWidth: "100px" }}
                        />
                      </td>
                      <td className="py-2 pr-4">
                        <select
                          value={room.room_type}
                          onChange={(e) => updateRoom(i, { room_type: e.target.value })}
                          className={inputCls}
                          style={{ minWidth: "120px" }}
                        >
                          {Object.values(RoomType).map((rt) => (
                            <option key={rt} value={rt}>
                              {formatRoomType(rt)}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2 pr-4 text-right">
                        <input
                          type="number"
                          min={0}
                          step={1}
                          value={room.area_sf}
                          onChange={(e) => updateRoom(i, { area_sf: Number(e.target.value) || 0 })}
                          className={`${inputCls} text-right font-mono`}
                          style={{ width: "90px" }}
                        />
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-[var(--color-navy-300)]">
                        {costData ? fmtSf(costData.cost_per_sf.expected) : "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-white">
                        {costData ? fmt(costData.total_cost.expected) : "—"}
                      </td>
                      <td className="py-2.5 pr-4 text-right font-mono text-[var(--color-navy-400)]">
                        {costData ? `${costData.percent_of_total.toFixed(1)}%` : "—"}
                      </td>
                      <td className="py-2.5 text-center">
                        <SourceIcon source={room.source} />
                      </td>
                      <td className="py-2 text-center">
                        <button
                          type="button"
                          onClick={() => removeRoom(i)}
                          className="rounded p-1 text-[var(--color-navy-500)] transition-colors hover:text-red-400"
                          title="Remove room"
                        >
                          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Add room + Recalculate */}
          <div className="mt-4 flex items-center gap-3">
            <button
              type="button"
              onClick={addRoom}
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--color-navy-700)] px-3 py-2 text-xs font-medium text-[var(--color-navy-300)] transition-colors hover:border-[var(--color-navy-500)] hover:text-white"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              Add Room
            </button>
            {hasEdits && (
              <button
                type="button"
                onClick={handleRecalculate}
                disabled={recalculating}
                className="rounded-md bg-[var(--color-blueprint-500)] px-4 py-2 text-xs font-bold text-white transition-all hover:bg-[var(--color-blueprint-400)] hover:shadow-lg disabled:opacity-50"
              >
                {recalculating ? "Recalculating..." : "Recalculate"}
              </button>
            )}
            {recalcError && (
              <p className="text-xs text-red-400">{recalcError}</p>
            )}
          </div>
        </>
      ) : (
        <div className="rounded border border-[var(--color-navy-700)]/50 bg-[var(--color-navy-800)]/50 px-4 py-6 text-center">
          <p className="text-sm text-[var(--color-navy-400)]">
            No room-level breakdown available. The estimate uses a whole-building cost rate.
          </p>
          <p className="mt-1 text-xs text-[var(--color-navy-500)]">
            Upload a detailed floor plan with room labels for per-room cost analysis.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Building Parameters Editor ─────────────────────────────────────────────

function BuildingParametersEditor({
  model,
  confidence,
  onChange,
  hasChanges,
  recalculating,
  recalcError,
  onRecalculate,
}: {
  model: BuildingModel;
  confidence: Record<string, Confidence>;
  onChange: (m: BuildingModel) => void;
  hasChanges: boolean;
  recalculating: boolean;
  recalcError: string | null;
  onRecalculate: () => void;
}) {
  const update = (patch: Partial<BuildingModel>) => {
    onChange({ ...model, ...patch });
  };

  const inputCls =
    "w-full rounded-md border border-[var(--color-navy-700)] bg-[var(--color-navy-800)] px-3 py-2 text-sm text-white transition-colors focus:border-[var(--color-blueprint-500)] focus:outline-none";

  return (
    <div className="rounded-lg border border-[var(--color-navy-700)] bg-[var(--color-navy-900)] p-6">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-[var(--color-navy-300)]">
        Building Parameters
      </h3>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {/* Building Type */}
        <FieldWithConfidence label="Building Type" confidence={confidence.building_type}>
          <select
            value={model.building_type}
            onChange={(e) => update({ building_type: e.target.value as BuildingType })}
            className={inputCls}
          >
            {Object.values(BuildingType).map((v) => (
              <option key={v} value={v}>
                {BUILDING_TYPE_LABELS[v] ?? v}
              </option>
            ))}
          </select>
        </FieldWithConfidence>

        {/* Gross SF */}
        <FieldWithConfidence label="Gross SF" confidence={confidence.gross_sf}>
          <input
            type="number"
            min={1}
            value={model.gross_sf}
            onChange={(e) => update({ gross_sf: Number(e.target.value) || 1 })}
            className={inputCls}
          />
        </FieldWithConfidence>

        {/* Stories */}
        <FieldWithConfidence label="Stories" confidence={confidence.stories}>
          <input
            type="number"
            min={1}
            value={model.stories}
            onChange={(e) => update({ stories: Number(e.target.value) || 1 })}
            className={inputCls}
          />
        </FieldWithConfidence>

        {/* Story Height */}
        <FieldWithConfidence label="Story Height (ft)" confidence={confidence.story_height_ft}>
          <input
            type="number"
            min={1}
            step={0.5}
            value={model.story_height_ft}
            onChange={(e) => update({ story_height_ft: Number(e.target.value) || 1 })}
            className={inputCls}
          />
        </FieldWithConfidence>

        {/* Structural System */}
        <FieldWithConfidence label="Structural System" confidence={confidence.structural_system}>
          <select
            value={model.structural_system}
            onChange={(e) => update({ structural_system: e.target.value as StructuralSystem })}
            className={inputCls}
          >
            {Object.values(StructuralSystem).map((v) => (
              <option key={v} value={v}>
                {STRUCTURAL_LABELS[v] ?? v}
              </option>
            ))}
          </select>
        </FieldWithConfidence>

        {/* Exterior Wall */}
        <FieldWithConfidence label="Exterior Wall" confidence={confidence.exterior_wall_system}>
          <select
            value={model.exterior_wall_system}
            onChange={(e) => update({ exterior_wall_system: e.target.value as ExteriorWall })}
            className={inputCls}
          >
            {Object.values(ExteriorWall).map((v) => (
              <option key={v} value={v}>
                {EXTERIOR_LABELS[v] ?? v}
              </option>
            ))}
          </select>
        </FieldWithConfidence>

        {/* City */}
        <FieldWithConfidence label="City" confidence={confidence.location}>
          <input
            type="text"
            value={model.location.city}
            onChange={(e) =>
              update({ location: { ...model.location, city: e.target.value } })
            }
            className={inputCls}
          />
        </FieldWithConfidence>

        {/* State */}
        <FieldWithConfidence label="State" confidence={confidence.location}>
          <select
            value={model.location.state}
            onChange={(e) =>
              update({ location: { ...model.location, state: e.target.value } })
            }
            className={inputCls}
          >
            {US_STATES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </FieldWithConfidence>
      </div>

      {/* Recalculate button + error */}
      {hasChanges && (
        <div className="mt-5 flex items-center gap-4">
          <button
            type="button"
            onClick={onRecalculate}
            disabled={recalculating}
            className="rounded-md bg-[var(--color-blueprint-500)] px-5 py-2.5 text-sm font-bold text-white transition-all hover:bg-[var(--color-blueprint-400)] hover:shadow-lg disabled:opacity-50"
          >
            {recalculating ? "Recalculating..." : "Recalculate"}
          </button>
          {recalcError && (
            <p className="text-sm text-red-400">{recalcError}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Field with confidence badge ────────────────────────────────────────────

function FieldWithConfidence({
  label,
  confidence,
  children,
}: {
  label: string;
  confidence?: Confidence | string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <label className="text-xs font-medium text-[var(--color-navy-400)]">
          {label}
        </label>
        {confidence && <ConfidenceBadge confidence={confidence} />}
      </div>
      {children}
    </div>
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
