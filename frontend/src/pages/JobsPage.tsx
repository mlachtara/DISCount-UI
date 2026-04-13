/**
 * List all jobs + create-job form.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createJob, listImages, listJobs, listModels } from "../api/client";
import type { CVModelRecord, ImageRecord, Job } from "../types";

function StatusBadge({ status }: { status: Job["status"] }) {
  const cls: Record<string, string> = {
    created: "badge-created",
    processing: "badge-processing",
    ready: "badge-ready",
    error: "badge-error",
  };
  return <span className={cls[status] ?? "badge"}>{status}</span>;
}

export default function JobsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [images, setImages] = useState<ImageRecord[]>([]);
  const [models, setModels] = useState<CVModelRecord[]>([]);

  // ── form state ────────────────────────────────────────────────────────────
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [modelId, setModelId] = useState<number | "">("");
  const [selectedImages, setSelectedImages] = useState<Set<number>>(new Set());
  const [epsilon, setEpsilon] = useState(0.5);
  const [numTiles, setNumTiles] = useState(1);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    Promise.all([listJobs(), listImages(), listModels()]).then(([j, i, m]) => {
      setJobs(j);
      setImages(i);
      setModels(m);
    });
  }, []);

  function toggleImage(id: number) {
    setSelectedImages((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!modelId || selectedImages.size === 0) {
      setFormError("Select a model and at least one image.");
      return;
    }
    setCreating(true);
    setFormError("");
    try {
      const job = await createJob({
        name: name.trim(),
        description: desc.trim(),
        model_id: Number(modelId),
        image_ids: [...selectedImages],
        epsilon,
        num_tiles: Math.max(1, numTiles),
      });
      navigate(`/jobs/${job.id}`);
    } catch (err) {
      setFormError(String(err));
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-900">Jobs</h1>

      {/* ── Existing jobs ── */}
      {jobs.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-3">All jobs</h2>
          <ul className="divide-y divide-gray-100">
            {jobs.map((j) => (
              <li key={j.id} className="py-3 flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <Link
                    to={`/jobs/${j.id}`}
                    className="font-medium text-gray-900 hover:text-brand-600"
                  >
                    {j.name}
                  </Link>
                  {j.description && (
                    <p className="text-xs text-gray-400 mt-0.5 truncate">{j.description}</p>
                  )}
                  {j.status === "error" && j.error_message && (
                    <p className="text-xs text-red-500 mt-0.5">{j.error_message}</p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0 mt-0.5">
                  {j.status === "ready" && (
                    <div className="text-xs text-gray-500">
                      {j.labeled_tiles}/{j.total_tiles} labeled
                    </div>
                  )}
                  <StatusBadge status={j.status} />
                  {j.status === "ready" && (
                    <Link to={`/jobs/${j.id}/label`} className="btn-primary py-1 text-xs">
                      Label
                    </Link>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Create new job ── */}
      <div className="card">
        <h2 className="font-semibold text-gray-800 mb-4">Create new job</h2>

        {models.length === 0 && (
          <p className="text-sm text-amber-600 mb-3">
            No models yet.{" "}
            <Link to="/upload" className="underline">
              Upload a .pt model first.
            </Link>
          </p>
        )}
        {images.length === 0 && (
          <p className="text-sm text-amber-600 mb-3">
            No images yet.{" "}
            <Link to="/upload" className="underline">
              Upload images first.
            </Link>
          </p>
        )}

        <form onSubmit={handleCreate} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Job name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="e.g. Palu Tsunami 2018"
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-brand-400"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Detector model <span className="text-red-500">*</span>
              </label>
              <select
                value={modelId}
                onChange={(e) => setModelId(Number(e.target.value))}
                required
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm
                           focus:outline-none focus:ring-2 focus:ring-brand-400"
              >
                <option value="">— select model —</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={2}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Minimum g(s) (ε) — floor applied when the detector count is below this value, ensuring every tile has a non-zero sampling probability
            </label>
            <input
              type="number"
              value={epsilon}
              min={0}
              step={0.1}
              onChange={(e) => setEpsilon(Number(e.target.value))}
              className="w-32 border border-gray-300 rounded-md px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Tiles per image
            </label>
            <input
              type="number"
              value={numTiles}
              min={1}
              step={1}
              onChange={(e) => setNumTiles(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-32 border border-gray-300 rounded-md px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
            <p className="text-xs text-gray-400 mt-1">
              {numTiles <= 1
                ? "Each image is labeled as a single tile."
                : (() => {
                    const cols = Math.ceil(Math.sqrt(numTiles));
                    const rows = Math.ceil(numTiles / cols);
                    return `Each image will be split into a ${rows}×${cols} grid (${rows * cols} tiles). Useful when a single image contains thousands of objects.`;
                  })()
              }
            </p>
          </div>

          {/* Image selector */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Images <span className="text-red-500">*</span>{" "}
                <span className="text-gray-400 font-normal">
                  ({selectedImages.size} selected)
                </span>
              </label>
              <button
                type="button"
                className="text-xs text-brand-600 hover:underline"
                onClick={() =>
                  selectedImages.size === images.length
                    ? setSelectedImages(new Set())
                    : setSelectedImages(new Set(images.map((i) => i.id)))
                }
              >
                {selectedImages.size === images.length ? "Deselect all" : "Select all"}
              </button>
            </div>
            <div className="border border-gray-200 rounded-md divide-y max-h-52 overflow-y-auto text-sm">
              {images.map((img) => (
                <label
                  key={img.id}
                  className="flex items-center gap-3 px-3 py-2 hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedImages.has(img.id)}
                    onChange={() => toggleImage(img.id)}
                    className="rounded border-gray-300 text-brand-600"
                  />
                  <span className="truncate text-gray-700">{img.original_filename}</span>
                  {img.width && (
                    <span className="text-gray-400 shrink-0">
                      {img.width}×{img.height}
                    </span>
                  )}
                </label>
              ))}
              {images.length === 0 && (
                <p className="px-3 py-2 text-gray-400">No images uploaded yet.</p>
              )}
            </div>
          </div>

          {formError && <p className="text-sm text-red-600">{formError}</p>}

          <button
            type="submit"
            className="btn-primary"
            disabled={creating || !name.trim() || !modelId || selectedImages.size === 0}
          >
            {creating ? "Creating…" : "Create job & run detector"}
          </button>
        </form>
      </div>
    </div>
  );
}
