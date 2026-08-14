import type { SelectedImage } from "./types";

const ACCEPTED = [".jpg", ".jpeg", ".png", ".webp"];
const ACCEPTED_MIME = ["image/jpeg", "image/png", "image/webp", "image/jpg"];

let counter = 0;
function nextId(): string {
  counter += 1;
  return `local_${Date.now().toString(36)}_${counter}`;
}

export function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  const extOk = ACCEPTED.some((e) => name.endsWith(e));
  const mimeOk = !file.type || ACCEPTED_MIME.includes(file.type.toLowerCase());
  return extOk && mimeOk;
}

/**
 * Load a selected file into a {@link SelectedImage}: real pixel dimensions plus
 * a small downscaled thumbnail (data URL) generated locally. The original file
 * is kept for the before/after comparison and is never re-downloaded from the
 * backend.
 */
export async function loadSelectedImage(file: File): Promise<SelectedImage> {
  const previewUrl = URL.createObjectURL(file);
  const img = await loadImageElement(previewUrl);
  const thumbUrl = makeThumbnail(img, 420);
  return {
    localId: nextId(),
    file,
    previewUrl,
    thumbUrl,
    width: img.naturalWidth,
    height: img.naturalHeight,
  };
}

function loadImageElement(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve(el);
    el.onerror = () => reject(new Error("Could not read image."));
    el.src = url;
  });
}

function makeThumbnail(img: HTMLImageElement, maxEdge: number): string {
  const { naturalWidth: w, naturalHeight: h } = img;
  const scale = Math.min(1, maxEdge / Math.max(w, h));
  const tw = Math.max(1, Math.round(w * scale));
  const th = Math.max(1, Math.round(h * scale));
  const canvas = document.createElement("canvas");
  canvas.width = tw;
  canvas.height = th;
  const ctx = canvas.getContext("2d");
  if (!ctx) return img.src;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(img, 0, 0, tw, th);
  try {
    return canvas.toDataURL("image/jpeg", 0.82);
  } catch {
    return img.src;
  }
}

export function revokeSelected(img: SelectedImage): void {
  URL.revokeObjectURL(img.previewUrl);
}
