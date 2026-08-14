import type { AppConfig, JobResponse, ScanResponse, SelectedImage } from "./types";

/** Base URL for the backend API.
 *
 *  - Local dev: unset → "/api", which Vite proxies to the FastAPI backend.
 *  - Hosted frontend (e.g. Vercel): set VITE_API_BASE to the deployed backend
 *    origin, e.g. "https://qween-backend.onrender.com/api".
 *
 *  The FAL_KEY is never present in the frontend regardless. */
const RAW_BASE = (import.meta.env.VITE_API_BASE ?? "").trim().replace(/\/+$/, "");
const BASE = RAW_BASE || "/api";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status}).`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore parse errors */
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function fetchConfig(): Promise<AppConfig> {
  return jsonOrThrow<AppConfig>(await fetch(`${BASE}/config`));
}

export async function scan(
  images: SelectedImage[],
  scaleFactor: number,
  outputSuffix: string,
  outputFormat: string,
): Promise<ScanResponse> {
  const form = new FormData();
  for (const img of images) {
    form.append("images", img.file, img.file.name);
  }
  form.append("scale_factor", String(scaleFactor));
  form.append("output_suffix", outputSuffix);
  form.append("output_format", outputFormat);
  return jsonOrThrow<ScanResponse>(
    await fetch(`${BASE}/scan`, { method: "POST", body: form }),
  );
}

export async function startJob(
  scanId: string,
  concurrency: number,
): Promise<JobResponse> {
  return jsonOrThrow<JobResponse>(
    await fetch(`${BASE}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scan_id: scanId, confirmed: true, concurrency }),
    }),
  );
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return jsonOrThrow<JobResponse>(await fetch(`${BASE}/jobs/${jobId}`));
}

export async function retry(
  jobId: string,
  imageIds?: string[],
): Promise<JobResponse> {
  return jsonOrThrow<JobResponse>(
    await fetch(`${BASE}/jobs/${jobId}/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_ids: imageIds ?? null }),
    }),
  );
}

export function eventsUrl(jobId: string): string {
  return `${BASE}/jobs/${jobId}/events`;
}

export function resultDownloadUrl(resultId: string): string {
  return `${BASE}/results/${resultId}/download`;
}

export function resultPreviewUrl(resultId: string): string {
  return `${BASE}/results/${resultId}/preview`;
}

export function downloadAllUrl(jobId: string): string {
  return `${BASE}/jobs/${jobId}/download-all`;
}
