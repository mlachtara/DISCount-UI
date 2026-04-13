/**
 * Line chart: estimated count ± 95% CI vs. number of labeled tiles.
 * The estimate starts noisy and converges as more tiles are labeled.
 */
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EstimateHistoryPoint } from "../types";

interface Props {
  history: EstimateHistoryPoint[];
}

export default function EstimateChart({ history }: Props) {
  if (history.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
        Submit your first label to see the estimate.
      </div>
    );
  }

  const data = history.map((h) => ({
    n: h.n_labeled,
    estimate: +h.estimate.toFixed(2),
    ci_lower: h.ci_lower != null ? +h.ci_lower.toFixed(2) : null,
    ci_upper: h.ci_upper != null ? +h.ci_upper.toFixed(2) : null,
    // recharts Area needs [lower, upper] as a range
    ciRange:
      h.ci_lower != null && h.ci_upper != null
        ? [+h.ci_lower.toFixed(2), +h.ci_upper.toFixed(2)]
        : null,
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="n"
          label={{ value: "Tiles labeled", position: "insideBottom", offset: -2, fontSize: 12 }}
          tick={{ fontSize: 11 }}
        />
        <YAxis tick={{ fontSize: 11 }} width={55} />
        <Tooltip
          formatter={(v: number, name: string) => {
            if (name === "ciRange") return null;
            return [v.toFixed(1), name === "estimate" ? "Estimate" : name];
          }}
        />
        <Legend verticalAlign="top" height={28} />

        {/* 95% CI shaded band */}
        <Area
          dataKey="ciRange"
          name="95% CI"
          fill="#93c5fd"
          stroke="none"
          fillOpacity={0.4}
          connectNulls
          dot={false}
          activeDot={false}
          legendType="rect"
        />

        {/* Estimate line */}
        <Line
          type="monotone"
          dataKey="estimate"
          name="Estimate"
          stroke="#2563eb"
          strokeWidth={2}
          dot={{ r: 3 }}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
