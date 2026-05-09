// ── Mirrors backend Pydantic schemas ─────────────────────────────────────────

export interface User {
  id: number;
  username: string;
  created_at: string;
}

export interface ImageRecord {
  id: number;
  original_filename: string;
  file_size: number | null;
  width: number | null;
  height: number | null;
  uploaded_at: string;
}

export interface CVModelRecord {
  id: number;
  name: string;
  filename: string;
  original_filename: string;
  file_size: number | null;
  uploaded_at: string;
}

export interface Job {
  id: number;
  name: string;
  description: string;
  model_id: number;
  status: "created" | "processing" | "ready" | "error";
  epsilon: number;
  created_at: string;
  error_message: string | null;
  total_tiles: number;
  labeled_tiles: number;
}

export interface Tile {
  id: number;
  job_id: number;
  image_id: number;
  g_count: number;
  g_count_raw: number;
  detections_json: string;  // JSON-encoded Detection[]
  is_labeled: boolean;
  image_url: string;        // cropped sub-tile URL (or full image when not tiled)
  tile_row: number;         // 0-based row index in the grid
  tile_col: number;         // 0-based column index in the grid
  grid_rows: number;        // total rows (1 = not tiled)
  grid_cols: number;        // total columns (1 = not tiled)
}

export interface Detection {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  confidence: number;
  class_id: number;
}

export interface LabelPoint {
  x: number;
  y: number;
}

export interface Label {
  id: number;
  tile_id: number;
  job_id: number;
  f_count: number;
  label_points_json: string;  // JSON-encoded LabelPoint[] in tile-pixel coordinates
  labeled_at: string;
}

export interface EstimateOut {
  job_id: number;
  n_labeled: number;
  total_tiles: number;
  estimate: number;
  ci_lower: number | null;
  ci_upper: number | null;
  std_error: number | null;
  g_total: number;
}

export interface EstimateHistoryPoint {
  n_labeled: number;
  estimate: number;
  ci_lower: number | null;
  ci_upper: number | null;
  std_error: number | null;
  computed_at: string;
}
