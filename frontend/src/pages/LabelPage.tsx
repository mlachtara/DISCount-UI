/**
 * Core labeling interface.
 *
 * Tile image is shown with:
 *   • Yellow bounding boxes  — detector proposals (g(s))
 *   • Green numbered circles — click-points added by the labeler (f(s))
 *
 * Click anywhere on the image to add a count point.
 * Click an existing point to remove it.
 * The count input always reflects the current number of points;
 * typing a number directly clears the visual points and sets the raw count.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getEstimateHistory, getJob, nextTile, submitLabel } from "../api/client";
import EstimateChart from "../components/EstimateChart";
import StdErrorChart from "../components/StdErrorChart";
import type { Detection, EstimateHistoryPoint, EstimateOut, Job, Tile } from "../types";

// ── Canvas drawing ────────────────────────────────────────────────────────────

interface Point {
  x: number; // in natural image pixel coordinates
  y: number;
}

function drawOverlay(
  canvas: HTMLCanvasElement,
  img: HTMLImageElement,
  detections: Detection[],
  points: Point[]
) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const lw = Math.max(2, canvas.width / 400);

  // ── Detector bounding boxes (yellow) ──
  for (const d of detections) {
    ctx.strokeStyle = "rgba(250, 204, 21, 0.9)";
    ctx.lineWidth = lw;
    ctx.strokeRect(d.x1, d.y1, d.x2 - d.x1, d.y2 - d.y1);

    const label = `${(d.confidence * 100).toFixed(0)}%`;
    const fontSize = Math.max(10, canvas.width / 70);
    ctx.font = `bold ${fontSize}px sans-serif`;
    const tw = ctx.measureText(label).width + 6;
    ctx.fillStyle = "rgba(250, 204, 21, 0.85)";
    ctx.fillRect(d.x1, d.y1 - fontSize - 4, tw, fontSize + 4);
    ctx.fillStyle = "#1c1917";
    ctx.fillText(label, d.x1 + 3, d.y1 - 4);
  }

  // ── Human click-points (green numbered circles) ──
  const r = Math.max(10, canvas.width / 60);
  for (let i = 0; i < points.length; i++) {
    const { x, y } = points[i];
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(34, 197, 94, 0.85)";
    ctx.fill();
    ctx.strokeStyle = "white";
    ctx.lineWidth = lw * 1.5;
    ctx.stroke();

    ctx.fillStyle = "white";
    ctx.font = `bold ${r * 1.1}px sans-serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(i + 1), x, y);
  }
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function LabelPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const id = Number(jobId);

  const [job, setJob] = useState<Job | null>(null);
  const [tile, setTile] = useState<Tile | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [loadingTile, setLoadingTile] = useState(true);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  // ── Click-point state ──
  const [points, setPoints] = useState<Point[]>([]);
  // fCount tracks the authoritative count; driven by points or manual input
  const [fCount, setFCount] = useState<number | "">(0);

  // ── Estimate / history ──
  const [estimate, setEstimate] = useState<EstimateOut | null>(null);
  const [history, setHistory] = useState<EstimateHistoryPoint[]>([]);

  // ── Canvas / image refs ──
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Parse detections from current tile
  const detections: Detection[] = (() => {
    if (!tile) return [];
    try {
      return JSON.parse(tile.detections_json) as Detection[];
    } catch {
      return [];
    }
  })();

  // ── Redraw canvas whenever points or tile changes ──
  const redraw = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.complete || !img.naturalWidth) return;
    drawOverlay(canvas, img, detections, points);
  }, [tile?.id, points]); // detections derived from tile

  useEffect(() => {
    redraw();
  }, [redraw]);

  // ── Initial load ──
  useEffect(() => {
    if (!id) return;
    getJob(id).then(setJob).catch((e) => setError(String(e)));
    loadNextTile();
    getEstimateHistory(id).then(setHistory);
  }, [id]);

  async function loadNextTile() {
    setLoadingTile(true);
    setPoints([]);
    setFCount(0);
    try {
      const t = await nextTile(id);
      if (!t) {
        setDone(true);
        setTile(null);
      } else {
        setTile(t);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingTile(false);
    }
  }

  // ── Canvas click handler ──
  function handleCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;

    const rect = canvas.getBoundingClientRect();
    // Map CSS pixels → natural image pixels
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;

    // Hit radius scales with image size so it stays ~12 CSS px
    const hitRadius = 12 * Math.max(scaleX, scaleY);
    const nearIdx = points.findIndex(
      (p) => Math.hypot(p.x - x, p.y - y) <= hitRadius
    );

    let next: Point[];
    if (nearIdx >= 0) {
      // Remove existing point
      next = points.filter((_, i) => i !== nearIdx);
    } else {
      // Add new point
      next = [...points, { x, y }];
    }
    setPoints(next);
    setFCount(next.length);
  }

  // ── Manual count input ──
  function handleCountInput(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value;
    if (val === "") {
      setFCount("");
    } else {
      const n = Math.max(0, parseInt(val, 10) || 0);
      setFCount(n);
      // Clear visual points since they no longer reflect the typed value
      setPoints([]);
    }
  }

  // ── Submit label ──
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tile || fCount === "") return;
    setSubmitting(true);
    setError("");
    try {
      const est = await submitLabel(id, tile.id, Number(fCount));
      setEstimate(est);
      setHistory((prev) => [
        ...prev,
        {
          n_labeled: est.n_labeled,
          estimate: est.estimate,
          ci_lower: est.ci_lower,
          ci_upper: est.ci_upper,
          std_error: est.std_error,
          computed_at: new Date().toISOString(),
        },
      ]);
      getJob(id).then(setJob);
      await loadNextTile();
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  if (!job && !error) return <p className="text-gray-500">Loading…</p>;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Page header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-gray-900">{job?.name ?? "Label tiles"}</h1>
          {job && (
            <p className="text-sm text-gray-500 mt-0.5">
              {job.labeled_tiles} / {job.total_tiles} tiles labeled
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Link to={`/jobs/${id}/results`} className="btn-secondary">
            Results →
          </Link>
          <Link to={`/jobs/${id}`} className="btn-secondary">
            ← Job overview
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ── Left: tile canvas + form ── */}
        <div className="space-y-3">
          {/* Tile viewer */}
          <div className="card p-2">
            {loadingTile ? (
              <div className="h-64 flex items-center justify-center text-gray-400 text-sm">
                Loading tile…
              </div>
            ) : done ? (
              <div className="h-64 flex flex-col items-center justify-center gap-3 text-center">
                <div className="text-4xl">🎉</div>
                <p className="font-semibold text-gray-800">All tiles labeled!</p>
                <p className="text-sm text-gray-500">
                  Check the results page for the final estimate.
                </p>
                <Link to={`/jobs/${id}/results`} className="btn-primary mt-1">
                  View results
                </Link>
              </div>
            ) : tile ? (
              <div className="relative w-full select-none">
                <img
                  ref={imgRef}
                  src={tile.image_url}
                  alt={`Tile ${tile.id}`}
                  className="w-full rounded block"
                  draggable={false}
                  onLoad={redraw}
                />
                <canvas
                  ref={canvasRef}
                  className="absolute inset-0 w-full h-full rounded cursor-crosshair"
                  onClick={handleCanvasClick}
                />
              </div>
            ) : null}
          </div>

          {/* Hint */}
          {tile && !loadingTile && !done && (
            <p className="text-xs text-gray-500 text-center">
              Click the image to place a count marker · click an existing marker to remove it
            </p>
          )}

          {/* Tile position badge (only shown when image is tiled) */}
          {tile && !loadingTile && tile.grid_rows * tile.grid_cols > 1 && (
            <p className="text-xs text-center font-medium text-brand-700 bg-brand-50 rounded px-2 py-1">
              Tile row {tile.tile_row + 1}/{tile.grid_rows}, col {tile.tile_col + 1}/{tile.grid_cols}
              &nbsp;&mdash;&nbsp;{tile.grid_rows}&times;{tile.grid_cols} grid
            </p>
          )}

          {/* Detector info */}
          {tile && !loadingTile && (
            <p className="text-xs text-gray-400 text-center">
              Detector proposals:{" "}
              <strong className="text-gray-600">{tile.g_count_raw.toFixed(0)}</strong>{" "}
              &nbsp;·&nbsp; g(s) ={" "}
              <strong className="text-gray-600">{tile.g_count.toFixed(3)}</strong>
            </p>
          )}

          {/* Count form */}
          {!done && (
            <form onSubmit={handleSubmit} className="card space-y-3">
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Your count (f(s))
                  </label>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="w-8 h-8 rounded border border-gray-300 text-lg font-bold
                                 hover:bg-gray-100 disabled:opacity-40"
                      onClick={() => {
                        const next = points.slice(0, -1);
                        setPoints(next);
                        setFCount(next.length);
                      }}
                      disabled={submitting || loadingTile || points.length === 0 || fCount === "" || (typeof fCount === "number" && fCount <= 0)}
                    >
                      −
                    </button>
                    <input
                      type="number"
                      min={0}
                      step={1}
                      value={fCount}
                      onChange={handleCountInput}
                      className="w-20 border border-gray-300 rounded-md px-2 py-1.5 text-center
                                 text-xl font-bold focus:outline-none focus:ring-2 focus:ring-brand-400"
                      disabled={submitting || loadingTile || done}
                    />
                    <button
                      type="button"
                      className="w-8 h-8 rounded border border-gray-300 text-lg font-bold
                                 hover:bg-gray-100 disabled:opacity-40"
                      onClick={() => {
                        // +1 without a visual point (for fast incrementing)
                        const n = typeof fCount === "number" ? fCount + 1 : 1;
                        setFCount(n);
                        setPoints([]);  // clear points since they'd be off-count
                      }}
                      disabled={submitting || loadingTile}
                    >
                      +
                    </button>
                  </div>
                  {points.length > 0 && (
                    <p className="text-xs text-green-600 mt-1">
                      {points.length} marker{points.length !== 1 ? "s" : ""} placed on image
                    </p>
                  )}
                </div>

                <button
                  type="submit"
                  className="btn-primary self-end"
                  disabled={submitting || loadingTile || done || fCount === ""}
                >
                  {submitting ? "Saving…" : "Submit →"}
                </button>
              </div>

              {error && <p className="text-sm text-red-600">{error}</p>}
            </form>
          )}
        </div>

        {/* ── Right: live estimate ── */}
        <div className="space-y-4">
          {estimate ? (
            <div className="card text-center space-y-1">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                k-DISCOUNT estimate
              </p>
              <p className="text-4xl font-bold text-brand-700">
                {estimate.estimate.toFixed(1)}
              </p>
              {estimate.ci_lower != null && estimate.ci_upper != null ? (
                <p className="text-sm text-gray-500">
                  95% CI: [{estimate.ci_lower.toFixed(1)}, {estimate.ci_upper.toFixed(1)}]
                </p>
              ) : (
                <p className="text-xs text-gray-400">CI available after 2+ labels</p>
              )}
              {estimate.std_error != null && (
                <p className="text-xs text-gray-400">
                  Std error: {estimate.std_error.toFixed(3)}
                </p>
              )}
              <p className="text-xs text-gray-400">
                Based on {estimate.n_labeled} / {estimate.total_tiles} tiles
              </p>
            </div>
          ) : (
            <div className="card text-center text-sm text-gray-400 py-6">
              Submit your first label to see the estimate.
            </div>
          )}

          {history.length > 0 && (
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Estimate convergence</h3>
              <EstimateChart history={history} />
            </div>
          )}

          {history.filter((h) => h.std_error != null).length >= 2 && (
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Standard error</h3>
              <StdErrorChart history={history} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
