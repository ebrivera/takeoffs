/**
 * Typed fetch wrappers for the Cantena API.
 */

import type { CostEstimate } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Upload a PDF floor plan and get a cost estimate.
 *
 * POSTs multipart form data to /api/analyze.
 */
export async function analyzePlan(
  file: File,
  location: { projectName: string; city: string; state: string },
): Promise<CostEstimate> {
  const form = new FormData();
  form.append("file", file);
  form.append("project_name", location.projectName);
  form.append("city", location.city);
  form.append("state", location.state);

  // TODO: Wire up to backend POST /api/analyze once US-105 is implemented
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

  return (await res.json()) as CostEstimate;
}
