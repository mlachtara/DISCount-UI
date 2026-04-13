/**
 * Job overview: status, tile grid, progress, links to label / results.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getJob, listTiles } from "../api/client";
import TileGrid from "../components/TileGrid";
import type { Job, Tile } from "../types";

function StatusBadge({ status }: { status: Job["status"] }) {
  const cls: Record<string, string> = {
    created: "badge-created",
    processing: "badge-processing",
    ready: "badge-ready",
    error: "badge-error",
  };
  return <span className={cls[status] ?? "badge"}>{status}</span>;
}

export default function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const id = Number(jobId);

  const [job, setJob] = useState<Job | null>(null);
  const [tiles, setTiles] = useState<Tile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    Promise.all([getJob(id), listTiles(id)])
      .then(([j, t]) => {
        setJob(j);
        setTiles(t);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  // Poll while job is processing
  useEffect(() => {
    if (!job || job.status !== "processing") return;
    const interval = setInterval(() => {
      Promise.all([getJob(id), listTiles(id)]).then(([j, t]) => {
        setJob(j);
        setTiles(t);
        if (j.status !== "processing") clearInterval(interval);
      });
    }, 3000);
    return () => clearInterval(interval);
  }, [job?.status, id]);

  if (loading) return <p className="text-gray-500">Loading…</p>;
  if (error) return <p className="text-red-600">{error}</p>;
  if (!job) return <p className="text-gray-500">Job not found.</p>;

  const pct = job.total_tiles > 0 ? (job.labeled_tiles / job.total_tiles) * 100 : 0;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-bold text-gray-900">{job.name}</h1>
            <StatusBadge status={job.status} />
          </div>
          {job.description && (
            <p className="text-sm text-gray-500">{job.description}</p>
          )}
          {job.status === "error" && job.error_message && (
            <p className="text-sm text-red-600 mt-1">{job.error_message}</p>
          )}
        </div>

        <div className="flex gap-2 shrink-0">
          {job.status === "ready" && (
            <>
              <Link to={`/jobs/${job.id}/label`} className="btn-primary">
                Label tiles
              </Link>
              <Link to={`/jobs/${job.id}/results`} className="btn-secondary">
                Results
              </Link>
            </>
          )}
          <Link to="/jobs" className="btn-secondary">
            ← All jobs
          </Link>
        </div>
      </div>

      {/* Stats bar */}
      <div className="card grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
        <div>
          <p className="text-2xl font-bold text-brand-700">{job.total_tiles}</p>
          <p className="text-xs text-gray-500 mt-0.5">Total tiles</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-green-600">{job.labeled_tiles}</p>
          <p className="text-xs text-gray-500 mt-0.5">Labeled</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-700">
            {job.total_tiles - job.labeled_tiles}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">Remaining</p>
        </div>
        <div>
          <p className="text-2xl font-bold text-gray-700">{job.epsilon}</p>
          <p className="text-xs text-gray-500 mt-0.5">Epsilon (ε)</p>
        </div>
      </div>

      {/* Progress bar */}
      {job.status === "ready" && job.total_tiles > 0 && (
        <div>
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Labeling progress</span>
            <span>{pct.toFixed(0)}%</span>
          </div>
          <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-500 rounded-full transition-all duration-500"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      {/* Processing indicator */}
      {job.status === "processing" && (
        <div className="card flex items-center gap-3 text-sm text-amber-700 bg-amber-50 border-amber-200">
          <svg
            className="animate-spin h-5 w-5 text-amber-500 shrink-0"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v8H4z"
            />
          </svg>
          Detector is running… page updates automatically every 3 s.
        </div>
      )}

      {/* Tile grid */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-800">
            Tile overview{tiles.length > 0 ? ` (${tiles.length})` : ""}
          </h2>
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded border-2 border-green-400" />
              Labeled
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded border-2 border-orange-400" />
              Highest g(s)
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-3 rounded border-2 border-gray-300" />
              Unlabeled
            </span>
          </div>
        </div>
        <TileGrid tiles={tiles} />
      </div>
    </div>
  );
}
