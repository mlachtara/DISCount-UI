import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listJobs } from "../api/client";
import type { Job } from "../types";

function StatusBadge({ status }: { status: Job["status"] }) {
  const cls = {
    created: "badge-created",
    processing: "badge-processing",
    ready: "badge-ready",
    error: "badge-error",
  }[status];
  return <span className={cls}>{status}</span>;
}

export default function HomePage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listJobs()
      .then((j) => setJobs(j.slice(0, 5)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      {/* Hero */}
      <div className="card bg-gradient-to-br from-brand-50 to-white">
        <h1 className="text-2xl font-bold text-brand-900 mb-1">
          DISCOUNT — Human-in-the-Loop Object Counting
        </h1>
        <p className="text-gray-600 max-w-2xl">
          Upload images and a YOLO detector, create a counting job, then label a small
          random sample of tiles. The{" "}
          <a
            href="https://arxiv.org/abs/2306.03151"
            target="_blank"
            rel="noreferrer"
            className="text-brand-600 hover:underline"
          >
            k-DISCOUNT estimator
          </a>{" "}
          uses importance sampling to produce an unbiased count with a 95% confidence
          interval — typically requiring <strong>9–12× fewer labels</strong> than
          exhaustive screening.
        </p>
        <div className="mt-4 flex gap-3">
          <Link to="/upload" className="btn-primary">
            Upload Images &amp; Model
          </Link>
          <Link to="/jobs" className="btn-secondary">
            View Jobs
          </Link>
        </div>
      </div>

      {/* Quick-start steps */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          {
            step: "1",
            title: "Upload",
            body: "Upload your image tiles and a .pt YOLO detector on the Upload page.",
            href: "/upload",
          },
          {
            step: "2",
            title: "Create a job",
            body: "Select images + model. The detector runs automatically in the background.",
            href: "/jobs",
          },
          {
            step: "3",
            title: "Label & estimate",
            body: "Label a handful of sampled tiles. Watch the estimate converge in real time.",
            href: "/jobs",
          },
        ].map(({ step, title, body, href }) => (
          <Link key={step} to={href} className="card hover:border-brand-300 transition-colors">
            <div className="text-3xl font-bold text-brand-200 mb-1">{step}</div>
            <h2 className="font-semibold text-gray-800 mb-1">{title}</h2>
            <p className="text-sm text-gray-500">{body}</p>
          </Link>
        ))}
      </div>

      {/* Recent jobs */}
      {!loading && jobs.length > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-800">Recent jobs</h2>
            <Link to="/jobs" className="text-sm text-brand-600 hover:underline">
              View all →
            </Link>
          </div>
          <ul className="divide-y divide-gray-100">
            {jobs.map((j) => (
              <li key={j.id} className="py-2 flex items-center justify-between gap-4">
                <div>
                  <Link
                    to={`/jobs/${j.id}`}
                    className="font-medium text-gray-900 hover:text-brand-600"
                  >
                    {j.name}
                  </Link>
                  {j.description && (
                    <p className="text-xs text-gray-400 truncate max-w-xs">{j.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs text-gray-400">
                    {j.labeled_tiles}/{j.total_tiles} labeled
                  </span>
                  <StatusBadge status={j.status} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
