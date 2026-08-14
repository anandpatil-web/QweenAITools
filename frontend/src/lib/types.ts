export type ImageStatus =
  | "queued"
  | "uploading"
  | "processing"
  | "downloading"
  | "done"
  | "failed"
  | "timeout";

export interface AppConfig {
  usd_to_inr: number;
  scale_min: number;
  scale_max: number;
  scale_default: number;
  creativity_min: number;
  creativity_max: number;
  creativity_default: number;
  usd_per_megapixel: number;
  allowed_concurrency: number[];
  default_scale_factor: number;
  default_concurrency: number;
  default_suffix?: string;
  default_output_format?: string;
  max_concurrency: number;
  max_file_size_mb: number;
  image_timeout_seconds: number;
  output_formats: string[];
  accepted_extensions: string[];
  fal_configured: boolean;
  supabase_configured?: boolean;
}

/** A file the user has selected, plus a locally-generated thumbnail. */
export interface SelectedImage {
  localId: string;
  file: File;
  previewUrl: string; // object URL for the original (used for before image)
  thumbUrl: string; // small downscaled data URL for the grid
  width: number;
  height: number;
}

export interface ScannedImage {
  id: string;
  filename: string;
  width: number;
  height: number;
  input_megapixels: number;
  output_width: number;
  output_height: number;
  output_megapixels: number;
  estimated_cost_usd: number;
  estimated_cost_inr: number;
}

export interface ScanError {
  filename: string;
  error: string;
}

export interface ScanResponse {
  scan_id: string;
  scale_factor: number;
  output_suffix: string;
  output_format: string;
  images: ScannedImage[];
  errors: ScanError[];
  total_images: number;
  total_input_megapixels: number;
  total_output_megapixels: number;
  total_cost_usd: number;
  total_cost_inr: number;
}

export interface ImageState {
  id: string;
  filename: string;
  status: ImageStatus;
  width: number;
  height: number;
  output_width: number;
  output_height: number;
  estimated_cost_usd: number;
  result_id: string | null;
  output_filename: string | null;
  error: string | null;
  duration_seconds: number | null;
}

export interface JobResponse {
  job_id: string;
  scale_factor: number;
  output_suffix: string;
  output_format: string;
  concurrency: number;
  status: string;
  total: number;
  completed: number;
  succeeded: number;
  failed: number;
  timed_out: number;
  images: ImageState[];
}

export type SseEvent =
  | { type: "snapshot"; job_id: string; total: number; completed: number; succeeded: number; failed: number; timed_out: number; images: { image_id: string; status: ImageStatus; result_id: string | null; output_filename: string | null; error: string | null }[] }
  | { type: "image_status"; image_id: string; status: ImageStatus; result_id?: string; output_filename?: string; error?: string }
  | { type: "job_progress"; completed: number; total: number }
  | { type: "job_complete"; job_id: string; total: number; completed: number; succeeded: number; failed: number; timed_out: number };
