/**
 * Line chart: standard error vs. number of labeled tiles.
 * Should approach zero as more tiles are labeled.
 */
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EstimateHistoryPoint } from "../types";

interface Props {
  history: EstimateHistoryPoint[];
}

export default function StdErrorChart({ history }: Props) {
  const withError = history.filter((h) => h.std_error != null);

  if (withError.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
        At least 2 labels needed to compute standard error.
      </div>
    );
  }

  const data = withError.map((h) => ({
    n: h.n_labeled,
    std_error: +(h.std_error as number).toFixed(2),
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="n"
          label={{ value: "Tiles labeled", position: "insideBottom", offset: -2, fontSize: 12 }}
          tick={{ fontSize: 11 }}
        />
        <YAxis tick={{ fontSize: 11 }} width={55} />
        <Tooltip formatter={(v: number) => [v.toFixed(2), "Std error"]} />
        <Line
          type="monotone"
          dataKey="std_error"
          name="Std error"
          stroke="#f97316"
          strokeWidth={2}
          dot={{ r: 3 }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
