/**
 * Typed API client.
 * All functions use the native fetch API proxied through Vite to FastAPI.
 */
import type {
  CVModelRecord,
  EstimateHistoryPoint,
  EstimateOut,
  ImageRecord,
  Job,
  Label,
  Tile,
  User,
} from "../types";

const BASE = "/api";

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function register(username: string, password: string): Promise<User> {
  return json(
    await fetch(`${BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    })
  );
}

export async function login(username: string, password: string): Promise<User> {
  return json(
    await fetch(`${BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    })
  );
}

export async function logout(): Promise<void> {
  await fetch(`${BASE}/auth/logout`, { method: "POST" });
}

export async function getMe(): Promise<User | null> {
  const res = await fetch(`${BASE}/auth/me`);
  if (res.status === 401) return null;
  return json(res);
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Images ────────────────────────────────────────────────────────────────────

export async function uploadImages(files: FileList): Promise<ImageRecord[]> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  return json(await fetch(`${BASE}/images/upload`, { method: "POST", body: form }));
}

export async function listImages(): Promise<ImageRecord[]> {
  return json(await fetch(`${BASE}/images`));
}

// ── Models ────────────────────────────────────────────────────────────────────

export async function uploadModel(
  name: string,
  modelKind: "auto" | "yolo_v8" | "csrnet" | "faster_rcnn",
  file: File
): Promise<CVModelRecord> {
  const form = new FormData();
  form.append("name", name);
  form.append("model_kind", modelKind);
  form.append("file", file);
  return json(await fetch(`${BASE}/models/upload`, { method: "POST", body: form }));
}

export async function listModels(): Promise<CVModelRecord[]> {
  return json(await fetch(`${BASE}/models`));
}

// ── Jobs ──────────────────────────────────────────────────────────────────────

export async function createJob(body: {
  name: string;
  description: string;
  model_id: number;
  image_ids: number[];
  epsilon: number;
  num_tiles: number;
}): Promise<Job> {
  return json(
    await fetch(`${BASE}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function listJobs(): Promise<Job[]> {
  return json(await fetch(`${BASE}/jobs`));
}

export async function getJob(id: number): Promise<Job> {
  return json(await fetch(`${BASE}/jobs/${id}`));
}

export async function listTiles(jobId: number): Promise<Tile[]> {
  return json(await fetch(`${BASE}/jobs/${jobId}/tiles`));
}

export async function nextTile(jobId: number): Promise<Tile | null> {
  return json(await fetch(`${BASE}/jobs/${jobId}/next-tile`));
}

// ── Labels ────────────────────────────────────────────────────────────────────

export async function submitLabel(
  jobId: number,
  tileId: number,
  fCount: number
): Promise<EstimateOut> {
  return json(
    await fetch(`${BASE}/jobs/${jobId}/labels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tile_id: tileId, f_count: fCount }),
    })
  );
}

export async function listLabels(jobId: number): Promise<Label[]> {
  return json(await fetch(`${BASE}/jobs/${jobId}/labels`));
}

// ── Estimates ─────────────────────────────────────────────────────────────────

export async function getEstimate(jobId: number): Promise<EstimateOut> {
  return json(await fetch(`${BASE}/jobs/${jobId}/estimate`));
}

export async function getEstimateHistory(
  jobId: number
): Promise<EstimateHistoryPoint[]> {
  return json(await fetch(`${BASE}/jobs/${jobId}/estimate/history`));
}
