/**
 * Line chart: estimated count ± 95% CI vs. number of labeled tiles.
 * The estimate starts noisy and converges as more tiles are labeled.
 *
 * CI band is rendered using two stacked Areas (base = ci_lower, delta =
 * ci_upper - ci_lower) to avoid the buggy array-value dataKey trick.
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

  const data = history.map((h) => {
    const point: Record<string, unknown> = {
      n: h.n_labeled,
      estimate: +h.estimate.toFixed(2),
    };
    if (h.ci_lower != null && h.ci_upper != null) {
      point.ci_lower = +h.ci_lower.toFixed(2);
      // delta is rendered as a stacked band on top of ci_lower
      point.ci_delta = +(h.ci_upper - h.ci_lower).toFixed(2);
    }
    return point;
  });

  const hasCi = data.some((d) => d.ci_lower != null);

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
            if (name === "ci_lower" || name === "ci_delta") return null;
            return [v.toFixed(1), name === "estimate" ? "Estimate" : name];
          }}
        />
        <Legend verticalAlign="top" height={28} />

        {/* 95% CI shaded band — two stacked areas avoids the array-value bug */}
        {hasCi && (
          <>
            <Area
              dataKey="ci_lower"
              stackId="ci"
              fill="transparent"
              stroke="none"
              connectNulls
              dot={false}
              activeDot={false}
              legendType="none"
            />
            <Area
              dataKey="ci_delta"
              stackId="ci"
              name="95% CI"
              fill="#93c5fd"
              stroke="none"
              fillOpacity={0.4}
              connectNulls
              dot={false}
              activeDot={false}
              legendType="rect"
            />
          </>
        )}

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
