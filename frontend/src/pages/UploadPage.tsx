/**
 * Upload images and detector model weights.
 */
import { useRef, useState } from "react";
import { listImages, listModels, uploadImages, uploadModel } from "../api/client";
import type { CVModelRecord, ImageRecord } from "../types";

type UploadState = "idle" | "uploading" | "done" | "error";

export default function UploadPage() {
  // ── Image upload ─────────────────────────────────────────────────────────
  const [imgState, setImgState] = useState<UploadState>("idle");
  const [imgError, setImgError] = useState("");
  const [uploadedImages, setUploadedImages] = useState<ImageRecord[]>([]);
  const imgInput = useRef<HTMLInputElement>(null);

  async function handleImageUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setImgState("uploading");
    setImgError("");
    try {
      const result = await uploadImages(files);
      setUploadedImages((prev) => [...result, ...prev]);
      setImgState("done");
    } catch (err) {
      setImgError(String(err));
      setImgState("error");
    }
    if (imgInput.current) imgInput.current.value = "";
  }

  // ── Model upload ──────────────────────────────────────────────────────────
  const [modelName, setModelName] = useState("");
  const [modelKind, setModelKind] = useState<"auto" | "yolo_v8" | "csrnet" | "faster_rcnn">("auto");
  const [modelFile, setModelFile] = useState<File | null>(null);
  const [modelState, setModelState] = useState<UploadState>("idle");
  const [modelError, setModelError] = useState("");
  const [uploadedModels, setUploadedModels] = useState<CVModelRecord[]>([]);
  const modelInput = useRef<HTMLInputElement>(null);

  async function handleModelUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!modelFile || !modelName.trim()) return;
    setModelState("uploading");
    setModelError("");
    try {
      const result = await uploadModel(modelName.trim(), modelKind, modelFile);
      setUploadedModels((prev) => [result, ...prev]);
      setModelState("done");
      setModelName("");
      setModelFile(null);
      if (modelInput.current) modelInput.current.value = "";
    } catch (err) {
      setModelError(String(err));
      setModelState("error");
    }
  }

  // ── Load existing on mount ────────────────────────────────────────────────
  useState(() => {
    listImages().then(setUploadedImages);
    listModels().then(setUploadedModels);
  });

  const fmtSize = (b: number | null) =>
    b == null ? "?" : b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${(b / 1e3).toFixed(0)} KB`;

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-xl font-bold text-gray-900">Upload</h1>

      {/* ── Image upload ── */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-gray-800">Image tiles</h2>
        <p className="text-sm text-gray-500">
          Upload JPEG, PNG, or TIFF files. Each file is one sample unit <em>s</em> in
          the DISCOUNT framework. Max 50 MB per file.
        </p>

        <div
          className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center
                      hover:border-brand-400 cursor-pointer transition-colors"
          onClick={() => imgInput.current?.click()}
        >
          <p className="text-sm text-gray-500">
            {imgState === "uploading"
              ? "Uploading…"
              : "Click or drag-and-drop image files here"}
          </p>
          <p className="text-xs text-gray-400 mt-1">JPEG · PNG · TIFF — multiple files OK</p>
        </div>
        <input
          ref={imgInput}
          type="file"
          multiple
          accept=".jpg,.jpeg,.png,.tif,.tiff,.bmp"
          className="hidden"
          onChange={handleImageUpload}
          disabled={imgState === "uploading"}
        />

        {imgState === "done" && (
          <p className="text-sm text-green-600">Images uploaded successfully.</p>
        )}
        {imgState === "error" && (
          <p className="text-sm text-red-600">{imgError}</p>
        )}

        {uploadedImages.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">
              {uploadedImages.length} image{uploadedImages.length !== 1 ? "s" : ""} in library
            </p>
            <ul className="divide-y divide-gray-100 max-h-48 overflow-y-auto text-sm">
              {uploadedImages.map((img) => (
                <li key={img.id} className="py-1 flex justify-between gap-4">
                  <span className="truncate text-gray-700">{img.original_filename}</span>
                  <span className="text-gray-400 shrink-0">
                    {img.width && img.height ? `${img.width}×${img.height}  ` : ""}
                    {fmtSize(img.file_size)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* ── Model upload ── */}
      <div className="card space-y-4">
        <h2 className="font-semibold text-gray-800">Upload model</h2>
        <p className="text-sm text-gray-500">
          Upload detector weights (.pt / .pth / .pth.tar / .tar). Use auto-detect
          or manually pick a detector family. Max 500 MB.
        </p>

        <form onSubmit={handleModelUpload} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Model name</label>
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g. YOLOv8-bird-roost"
              required
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm
                         focus:outline-none focus:ring-2 focus:ring-brand-400"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Detector family</label>
            <div className="relative">
              <select
                value={modelKind}
                onChange={(e) =>
                  setModelKind(e.target.value as "auto" | "yolo_v8" | "csrnet" | "faster_rcnn")
                }
                className="w-full appearance-none border border-gray-300 rounded-md px-3 py-2 pr-10 text-sm text-left bg-white leading-5
                           focus:outline-none focus:ring-2 focus:ring-brand-400"
              >
                <option value="auto">Auto-detect (recommended)</option>
                <option value="yolo_v8">YOLO-v8</option>
                <option value="csrnet">CSRNet</option>
                <option value="faster_rcnn">Faster R-CNN</option>
              </select>
              <span
                aria-hidden="true"
                className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-gray-500"
              >
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                  <path
                    fillRule="evenodd"
                    d="M5.23 7.21a.75.75 0 011.06.02L10 11.169l3.71-3.94a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                    clipRule="evenodd"
                  />
                </svg>
              </span>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Weights file
            </label>
            <input
              ref={modelInput}
              type="file"
              accept={
                modelKind === "yolo_v8"
                  ? ".pt"
                  : modelKind === "csrnet"
                    ? ".pth,.pt,.tar,.pth.tar"
                    : modelKind === "faster_rcnn"
                      ? ".pt"
                    : ".pt,.pth,.tar,.pth.tar"
              }
              required
              onChange={(e) => setModelFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-gray-500 file:mr-3 file:py-1.5
                         file:px-3 file:rounded file:border-0 file:text-sm
                         file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
            />
          </div>

          <button
            type="submit"
            className="btn-primary"
            disabled={!modelName.trim() || !modelFile || modelState === "uploading"}
          >
            {modelState === "uploading" ? "Uploading…" : "Upload model"}
          </button>

          {modelState === "done" && (
            <p className="text-sm text-green-600">Model uploaded successfully.</p>
          )}
          {modelState === "error" && (
            <p className="text-sm text-red-600">{modelError}</p>
          )}
        </form>

        {uploadedModels.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 mb-2">
              {uploadedModels.length} model{uploadedModels.length !== 1 ? "s" : ""} in library
            </p>
            <ul className="divide-y divide-gray-100 text-sm">
              {uploadedModels.map((m) => (
                <li key={m.id} className="py-1 flex justify-between gap-4">
                  <span className="font-medium text-gray-700">
                    {m.name}{" "}
                    <span className="text-xs text-gray-400">
                      ({m.model_kind === "csrnet" ? "CSRNet" : m.model_kind === "faster_rcnn" ? "Faster R-CNN" : "YOLO-v8"})
                    </span>
                  </span>
                  <span className="text-gray-400 shrink-0">{fmtSize(m.file_size)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
