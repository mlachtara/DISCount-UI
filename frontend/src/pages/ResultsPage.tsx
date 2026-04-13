/**
 * Full results page for a completed job.
 * Shows the current k-DISCOUNT estimate, both convergence charts,
 * and a table of all labeled tiles.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getEstimate, getEstimateHistory, getJob, listLabels, listTiles } from "../api/client";
import EstimateChart from "../components/EstimateChart";
import StdErrorChart from "../components/StdErrorChart";
import type { EstimateHistoryPoint, EstimateOut, Job, Label, Tile } from "../types";

export default function ResultsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const id = Number(jobId);

  const [job, setJob] = useState<Job | null>(null);
  const [estimate, setEstimate] = useState<EstimateOut | null>(null);
  const [history, setHistory] = useState<EstimateHistoryPoint[]>([]);
  const [tiles, setTiles] = useState<Tile[]>([]);
  const [labels, setLabels] = useState<Label[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    Promise.all([
      getJob(id),
      getEstimate(id),
      getEstimateHistory(id),
      listTiles(id),
      listLabels(id),
    ])
      .then(([j, est, hist, t, l]) => {
        setJob(j);
        setEstimate(est);
        setHistory(hist);
        setTiles(t);
        setLabels(l);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-gray-500">Loading…</p>;
  if (error) return <p className="text-red-600">{error}</p>;
  if (!job) return <p className="text-gray-500">Job not found.</p>;

  // Build lookup: tile_id → label
  const labelByTile = new Map(labels.map((l) => [l.tile_id, l]));
  const labeledTiles = tiles.filter((t) => t.is_labeled);

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Results — {job.name}</h1>
          {job.description && (
            <p className="text-sm text-gray-500 mt-0.5">{job.description}</p>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          {job.status === "ready" && (
            <Link to={`/jobs/${id}/label`} className="btn-primary">
              Continue labeling
            </Link>
          )}
          <Link to={`/jobs/${id}`} className="btn-secondary">
            ← Job overview
          </Link>
        </div>
      </div>

      {/* ── Estimate hero ── */}
      {estimate && (
        <div className="card bg-gradient-to-br from-brand-50 to-white text-center space-y-2 py-8">
          <p className="text-xs font-semibold text-brand-600 uppercase tracking-widest">
            k-DISCOUNT estimate
          </p>
          <p className="text-6xl font-bold text-brand-800">
            {estimate.estimate.toFixed(1)}
          </p>
          {estimate.ci_lower != null && estimate.ci_upper != null ? (
            <p className="text-lg text-gray-600">
              95% CI: [{estimate.ci_lower.toFixed(1)},&nbsp;{estimate.ci_upper.toFixed(1)}]
            </p>
          ) : (
            <p className="text-sm text-gray-400">Confidence interval available after 2+ labels</p>
          )}
          <div className="flex justify-center gap-8 pt-2 text-sm text-gray-500">
            <span>
              <strong className="text-gray-700">{estimate.n_labeled}</strong> tiles labeled
            </span>
            <span>
              <strong className="text-gray-700">{estimate.total_tiles}</strong> total tiles
            </span>
            <span>
              G(Ω) = <strong className="text-gray-700">{estimate.g_total.toFixed(2)}</strong>
            </span>
            {estimate.std_error != null && (
              <span>
                σ̂ = <strong className="text-gray-700">{estimate.std_error.toFixed(3)}</strong>
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Charts ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">Estimate convergence</h2>
          <EstimateChart history={history} />
        </div>
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">Standard error</h2>
          <StdErrorChart history={history} />
        </div>
      </div>

      {/* ── Labeled tiles table ── */}
      {labeledTiles.length > 0 && (
        <div className="card">
          <h2 className="font-semibold text-gray-800 mb-4">
            Labeled tiles ({labeledTiles.length})
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs text-gray-500 uppercase tracking-wide">
                  <th className="pb-2 pr-4">Tile</th>
                  <th className="pb-2 pr-4">Detector g(s)</th>
                  <th className="pb-2 pr-4">Human f(s)</th>
                  <th className="pb-2 pr-4">Weight w = f/g</th>
                  <th className="pb-2">Labeled at</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {labeledTiles.map((t) => {
                  const lbl = labelByTile.get(t.id);
                  const w = lbl ? lbl.f_count / t.g_count : null;
                  return (
                    <tr key={t.id} className="text-gray-700">
                      <td className="py-2 pr-4">
                        <div className="flex items-center gap-2">
                          <img
                            src={t.image_url}
                            alt={`Tile ${t.id}`}
                            className="w-10 h-10 object-cover rounded border border-gray-200"
                          />
                          <span className="text-gray-500">#{t.id}</span>
                        </div>
                      </td>
                      <td className="py-2 pr-4">{t.g_count.toFixed(3)}</td>
                      <td className="py-2 pr-4 font-semibold">
                        {lbl?.f_count ?? "—"}
                      </td>
                      <td className="py-2 pr-4">
                        {w != null ? w.toFixed(3) : "—"}
                      </td>
                      <td className="py-2 text-gray-400 text-xs">
                        {lbl
                          ? new Date(lbl.labeled_at).toLocaleString()
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* No labels yet */}
      {labeledTiles.length === 0 && (
        <div className="card text-center py-8 text-gray-400">
          <p className="text-sm">No tiles labeled yet.</p>
          {job.status === "ready" && (
            <Link to={`/jobs/${id}/label`} className="btn-primary mt-4 inline-block">
              Start labeling
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
