export function formatUsd(value: number): string {
  return `$${value.toFixed(value < 1 ? 3 : 2)}`;
}

export function formatInr(value: number): string {
  return `₹${Math.round(value).toLocaleString("en-IN")}`;
}

export function formatMegapixels(mp: number): string {
  if (mp >= 100) return `${mp.toFixed(0)} MP`;
  if (mp >= 10) return `${mp.toFixed(1)} MP`;
  return `${mp.toFixed(2)} MP`;
}

export function formatDimensions(w: number, h: number): string {
  return `${w.toLocaleString()} × ${h.toLocaleString()}`;
}

export function statusLabel(status: string): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "uploading":
      return "Uploading…";
    case "processing":
      return "Upscaling…";
    case "downloading":
      return "Downloading…";
    case "done":
      return "Done";
    case "failed":
      return "Failed";
    case "timeout":
      return "Timed out";
    default:
      return status;
  }
}
