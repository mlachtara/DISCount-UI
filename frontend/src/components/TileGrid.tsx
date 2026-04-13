/**
 * Overview grid showing all tiles for a job.
 * Color coding:
 *   gray  = unlabeled
 *   green = labeled
 *   ring  = tile with highest g_count (most important)
 */
import type { Tile } from "../types";

interface Props {
  tiles: Tile[];
}

export default function TileGrid({ tiles }: Props) {
  if (tiles.length === 0) {
    return <p className="text-gray-500 text-sm">No tiles yet — the detector is still running.</p>;
  }

  const maxG = Math.max(...tiles.map((t) => t.g_count));

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(80px,1fr))] gap-1">
      {tiles.map((tile) => {
        const isTop = tile.g_count === maxG;
        return (
          <div
            key={tile.id}
            title={`Tile #${tile.id}  g(s)=${tile.g_count_raw.toFixed(1)}  ${
              tile.is_labeled ? "✓ labeled" : "unlabeled"
            }`}
            className={`relative aspect-square overflow-hidden rounded border-2 transition-all ${
              tile.is_labeled
                ? "border-green-400"
                : isTop
                ? "border-orange-400"
                : "border-gray-200"
            }`}
          >
            <img
              src={tile.image_url}
              alt={`Tile ${tile.id}`}
              className="w-full h-full object-cover"
              loading="lazy"
            />
            {/* Badge: labeled count or g value */}
            <div
              className={`absolute bottom-0 left-0 right-0 text-center text-xs font-semibold py-0.5 ${
                tile.is_labeled
                  ? "bg-green-500/80 text-white"
                  : "bg-black/50 text-gray-200"
              }`}
            >
              {tile.is_labeled ? "✓" : tile.g_count_raw.toFixed(0)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
