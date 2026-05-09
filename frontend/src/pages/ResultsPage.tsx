/**
 * Full results page for a completed job.
 * Shows the current k-DISCOUNT estimate, both convergence charts,
 * and a table of all labeled tiles. Click a row to see marker coordinates.
 */
import { Fragment, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getEstimate, getEstimateHistory, getJob, listLabels, listTiles } from "../api/client";
import EstimateChart from "../components/EstimateChart";
import LabeledTilePreview from "../components/LabeledTilePreview";
import StdErrorChart from "../components/StdErrorChart";
import type { EstimateHistoryPoint, EstimateOut, Job, Label, LabelPoint, Tile } from "../types";

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
  const [expandedTileId, setExpandedTileId] = useState<number | null>(null);

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

  const labelByTile = new Map(labels.map((l) => [l.tile_id, l]));
  const labeledTiles = tiles.filter((t) => t.is_labeled);

  function parsePoints(lbl: Label | undefined): LabelPoint[] {
    if (!lbl) return [];
    try {
      return JSON.parse(lbl.label_points_json) as LabelPoint[];
    } catch {
      return [];
    }
  }

  function toggleExpand(tileId: number) {
    setExpandedTileId((prev) => (prev === tileId ? null : tileId));
  }

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
          <h2 className="font-semibold text-gray-800 mb-1">
            Labeled tiles ({labeledTiles.length})
          </h2>
          <p className="text-xs text-gray-400 mb-4">Click a row to see marker coordinates.</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs text-gray-500 uppercase tracking-wide">
                  <th className="pb-2 pr-4">Tile</th>
                  <th className="pb-2 pr-4">Detector g(s)</th>
                  <th className="pb-2 pr-4">Human f(s)</th>
                  <th className="pb-2 pr-4">Markers</th>
                  <th className="pb-2 pr-4">Weight w = f/g</th>
                  <th className="pb-2">Labeled at</th>
                </tr>
              </thead>
              <tbody>
                {labeledTiles.map((t) => {
                  const lbl = labelByTile.get(t.id);
                  const w = lbl ? lbl.f_count / t.g_count : null;
                  const points = parsePoints(lbl);
                  const isExpanded = expandedTileId === t.id;

                  return (
                    <Fragment key={t.id}>
                      <tr
                        className="border-t border-gray-100 text-gray-700 cursor-pointer hover:bg-gray-50 transition-colors"
                        onClick={() => toggleExpand(t.id)}
                      >
                        <td className="py-2 pr-4">
                          <div className="flex items-center gap-2">
                            <LabeledTilePreview
                              imageUrl={t.image_url}
                              labelPointsJson={lbl?.label_points_json ?? "[]"}
                              size={64}
                            />
                            <div>
                              <span className="text-gray-500">#{t.id}</span>
                              <div className="text-xs text-brand-500 mt-0.5">
                                {isExpanded ? "▲ hide" : "▼ details"}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="py-2 pr-4">{t.g_count.toFixed(3)}</td>
                        <td className="py-2 pr-4 font-semibold">{lbl?.f_count ?? "—"}</td>
                        <td className="py-2 pr-4 text-xs text-gray-500">
                          {points.length > 0 ? `${points.length} placed` : lbl ? "typed" : "—"}
                        </td>
                        <td className="py-2 pr-4">
                          {w != null ? w.toFixed(3) : "—"}
                        </td>
                        <td className="py-2 text-gray-400 text-xs">
                          {lbl ? new Date(lbl.labeled_at).toLocaleString() : "—"}
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="bg-gray-50 border-t border-gray-100">
                          <td colSpan={6} className="px-4 py-4">
                            <div className="flex gap-6 items-start">
                              {/* Larger preview */}
                              <LabeledTilePreview
                                imageUrl={t.image_url}
                                labelPointsJson={lbl?.label_points_json ?? "[]"}
                                size={200}
                              />

                              {/* Coordinate table */}
                              <div className="flex-1 min-w-0">
                                <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
                                  Marker coordinates (tile pixels)
                                </h3>
                                {points.length > 0 ? (
                                  <table className="text-xs w-full max-w-xs">
                                    <thead>
                                      <tr className="text-gray-400 text-left border-b border-gray-200">
                                        <th className="pb-1 pr-4">#</th>
                                        <th className="pb-1 pr-4">X (px)</th>
                                        <th className="pb-1">Y (px)</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-100 font-mono">
                                      {points.map((p, i) => (
                                        <tr key={i} className="text-gray-700">
                                          <td className="py-1 pr-4 text-gray-400">{i + 1}</td>
                                          <td className="py-1 pr-4">{p.x.toFixed(1)}</td>
                                          <td className="py-1">{p.y.toFixed(1)}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                ) : (
                                  <p className="text-xs text-gray-400 italic">
                                    No click coordinates — count was entered manually.
                                  </p>
                                )}

                                {/* Grid position if tiled */}
                                {t.grid_rows * t.grid_cols > 1 && (
                                  <p className="text-xs text-gray-400 mt-3">
                                    Grid position: row {t.tile_row + 1}/{t.grid_rows}, col {t.tile_col + 1}/{t.grid_cols}
                                  </p>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
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
