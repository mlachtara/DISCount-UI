/**
 * Renders a tile thumbnail with the saved label click-markers drawn on top.
 * Points are stored in natural image pixel coordinates; the canvas scales them
 * to whatever CSS size is requested.
 */
import { useEffect, useRef } from "react";

interface LabelPoint {
  x: number;
  y: number;
}

interface Props {
  imageUrl: string;
  labelPointsJson: string; // JSON-encoded LabelPoint[]
  size?: number;           // CSS display size in px (default 80)
}

export default function LabeledTilePreview({ imageUrl, labelPointsJson, size = 80 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  let points: LabelPoint[] = [];
  try {
    points = JSON.parse(labelPointsJson) as LabelPoint[];
  } catch {
    // malformed JSON — render image only
  }

  function draw() {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !img.naturalWidth) return;

    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (points.length === 0) return;

    const r = Math.max(6, canvas.width / 80);
    const lw = Math.max(1.5, canvas.width / 300);

    for (let i = 0; i < points.length; i++) {
      const { x, y } = points[i];
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(47, 112, 231, 0.85)";
      ctx.fill();
      ctx.strokeStyle = "white";
      ctx.lineWidth = lw;
      ctx.stroke();

      ctx.fillStyle = "white";
      ctx.font = `bold ${r * 1.1}px sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(i + 1), x, y);
    }
  }

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;
    if (img.complete && img.naturalWidth) {
      draw();
    }
  });

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <img
        ref={imgRef}
        src={imageUrl}
        alt="Labeled tile"
        className="w-full h-full object-cover rounded border border-gray-200"
        draggable={false}
        onLoad={draw}
      />
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full rounded pointer-events-none"
      />
    </div>
  );
}
