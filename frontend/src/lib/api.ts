/**
 * Typed fetch wrappers for the Cantena API.
 */

import type { AnalyzeResponse, BuildingModel, CostEstimate, SpaceCost } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Upload a PDF floor plan and get a cost estimate.
 *
 * POSTs multipart form data to /api/analyze.
 */
export async function analyzePlan(
  file: File,
  location: { projectName: string; city: string; state: string },
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("project_name", location.projectName);
  form.append("city", location.city);
  form.append("state", location.state);

  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message =
      body && typeof body === "object" && "detail" in body
        ? String(body.detail)
        : `Analysis failed (${res.status})`;
    throw new Error(message);
  }

  return (await res.json()) as AnalyzeResponse;
}

/**
 * Recalculate a cost estimate from an edited BuildingModel
 * with optional SpaceProgram for room-type-aware pricing.
 *
 * POSTs JSON to /api/estimate (no PDF, no VLM).
 */
export async function estimateFromModel(
  building: BuildingModel,
  spaceProgram?: { spaces: SpaceCost[]; building_type: string } | null,
): Promise<CostEstimate> {
  const res = await fetch(`${API_BASE}/api/estimate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      building,
      space_program: spaceProgram ?? null,
    }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message =
      body && typeof body === "object" && "detail" in body
        ? String(body.detail)
        : `Estimate failed (${res.status})`;
    throw new Error(message);
  }

  return (await res.json()) as CostEstimate;
}

/**
 * Fetch the pre-built sample estimate (no API key needed).
 */
export async function getSampleEstimate(): Promise<AnalyzeResponse> {
  const res = await fetch(`${API_BASE}/api/sample-estimate`);

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const message =
      body && typeof body === "object" && "detail" in body
        ? String(body.detail)
        : `Failed to load sample (${res.status})`;
    throw new Error(message);
  }

  return (await res.json()) as AnalyzeResponse;
}
