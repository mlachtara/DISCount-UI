/**
 * About page: paper attribution, method description, workflow summary.
 */
export default function AboutPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-xl font-bold text-gray-900">About</h1>

      {/* Paper card */}
      <div className="card space-y-3">
        <h2 className="font-semibold text-gray-800 text-lg">The DISCOUNT framework</h2>
        <p className="text-sm text-gray-600">
          This tool implements the{" "}
          <strong>k-DISCOUNT</strong> estimator introduced in:
        </p>
        <blockquote className="border-l-4 border-brand-300 pl-4 text-sm text-gray-700 space-y-1">
          <p className="font-medium">
            "DISCOUNT: Human-in-the-Loop Object Counting via Importance Sampling"
          </p>
          <p className="text-gray-500">
            Gustavo Perez, Subhransu Maji, Daniel Sheldon (2023)
          </p>
          <a
            href="https://arxiv.org/abs/2306.03151"
            target="_blank"
            rel="noreferrer"
            className="text-brand-600 hover:underline text-xs"
          >
            arXiv:2306.03151
          </a>
        </blockquote>
        <p className="text-sm text-gray-600">
          DISCOUNT replaces exhaustive human screening with <em>importance sampling</em>:
          the detector assigns a probability g(s) to each image tile, and a small random
          sample is drawn proportional to those probabilities. A human labels only the
          sampled tiles. The estimator corrects for the sampling bias using importance
          weights w(s) = f(s)/g(s), producing an unbiased count with a 95% confidence
          interval — typically requiring <strong>9–12× fewer labels</strong> than
          looking at every tile.
        </p>
      </div>

      {/* Math card */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-gray-800">Estimator formula</h2>

        <div className="overflow-x-auto">
          <table className="text-sm w-full">
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="py-2 pr-6 font-mono text-brand-700 whitespace-nowrap">G(Ω)</td>
                <td className="py-2 text-gray-600">
                  Sum of all detector scores g(s) over the image set Ω
                </td>
              </tr>
              <tr>
                <td className="py-2 pr-6 font-mono text-brand-700 whitespace-nowrap">ε</td>
                <td className="py-2 text-gray-600">
                  Minimum floor for g(s): g(s) = max(raw_count, ε). Only takes effect
                  when the detector finds fewer objects than ε — tiles with detections
                  above ε are unaffected. Ensures every tile has a non-zero sampling
                  probability.
                </td>
              </tr>
              <tr>
                <td className="py-2 pr-6 font-mono text-brand-700 whitespace-nowrap">wᵢ = f(sᵢ)/g(sᵢ)</td>
                <td className="py-2 text-gray-600">
                  Importance weight for tile i: human count divided by detector score
                </td>
              </tr>
              <tr>
                <td className="py-2 pr-6 font-mono text-brand-700 whitespace-nowrap">w̄</td>
                <td className="py-2 text-gray-600">
                  Mean importance weight over labeled tiles
                </td>
              </tr>
              <tr>
                <td className="py-2 pr-6 font-mono text-brand-700 whitespace-nowrap">F̂ = G(Ω) · w̄</td>
                <td className="py-2 text-gray-600">
                  k-DISCOUNT point estimate of total object count
                </td>
              </tr>
              <tr>
                <td className="py-2 pr-6 font-mono text-brand-700 whitespace-nowrap">
                  CI = F̂ ± 1.96·G(Ω)·σ̂/√n
                </td>
                <td className="py-2 text-gray-600">
                  95% confidence interval (requires n ≥ 2 labeled tiles)
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Workflow card */}
      <div className="card space-y-3">
        <h2 className="font-semibold text-gray-800">Workflow</h2>
        <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
          <li>
            <strong>Upload</strong> your image tiles (JPEG/PNG/TIFF) and a YOLOv8
            detector model (<code>.pt</code>).
          </li>
          <li>
            <strong>Create a job</strong> by selecting the images and model. The detector
            runs in the background and computes g(s) for every tile.
          </li>
          <li>
            <strong>Label tiles</strong> one at a time. Tiles are sampled proportional to
            g(s), so high-probability tiles appear more often. For each tile you see the
            detector's bounding-box overlay and enter your own count f(s).
          </li>
          <li>
            <strong>Watch the estimate</strong> converge. After each label the charts
            update: the estimate stabilises and the standard error decreases.
          </li>
          <li>
            <strong>Stop whenever the CI is narrow enough</strong> for your use case —
            you don't need to label everything.
          </li>
        </ol>
      </div>

      {/* Tech stack */}
      <div className="card space-y-2">
        <h2 className="font-semibold text-gray-800">Tech stack</h2>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>
            <strong>Backend</strong> — Python 3.11 · FastAPI · SQLAlchemy (async/SQLite) ·
            Ultralytics YOLOv8 · Azure Blob Storage
          </li>
          <li>
            <strong>Frontend</strong> — React 18 · TypeScript · Vite · Tailwind CSS ·
            Recharts · React Router v6
          </li>
        </ul>
      </div>
    </div>
  );
}
