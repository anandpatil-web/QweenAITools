import { useEffect, useState } from "react";
import { AppShell, type ToolId } from "./components/AppShell";
import { UpscalerTool } from "./tools/upscaler/UpscalerTool";
import { SkinFixTool } from "./tools/skinfix/SkinFixTool";
import { fetchConfig } from "./lib/api";
import type { AppConfig } from "./lib/types";

// Used when the backend can't be reached (e.g. the frontend is deployed to
// Vercel with no backend yet). The full UI still renders so the design is
// visible; processing is disabled until a backend is connected.
const FALLBACK_CONFIG: AppConfig = {
  usd_to_inr: 90,
  scale_min: 1,
  scale_max: 200,
  scale_default: 2,
  creativity_min: 0,
  creativity_max: 10,
  creativity_default: 0,
  usd_per_megapixel: 0.016,
  allowed_concurrency: [1, 2, 4, 8],
  default_scale_factor: 2,
  default_concurrency: 4,
  default_suffix: "",
  default_output_format: "jpeg",
  max_concurrency: 4,
  max_file_size_mb: 50,
  image_timeout_seconds: 180,
  output_formats: ["jpeg", "png"],
  accepted_extensions: ["jpg", "jpeg", "png", "webp"],
  fal_configured: false,
  supabase_configured: false,
  openai_configured: false,
};

export function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [previewMode, setPreviewMode] = useState(false);
  const [tool, setTool] = useState<ToolId>("upscaler");

  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch(() => {
        setConfig(FALLBACK_CONFIG);
        setPreviewMode(true);
      });
  }, []);

  return (
    <AppShell activeTool={tool} onSelectTool={setTool}>
      {previewMode && (
        <div className="qw-banner qw-banner--warn">
          <span>
            <b>Preview mode.</b> The backend isn’t connected, so processing is
            disabled. Run the app locally (<code>npm run dev</code>) or host the
            backend and set <code>VITE_API_BASE</code> to enable it.
          </span>
        </div>
      )}
      {!config && (
        <div className="qw-eyebrow" style={{ padding: "40px 0" }}>
          Loading…
        </div>
      )}
      {config && tool === "upscaler" && (
        <UpscalerTool config={config} previewMode={previewMode} />
      )}
      {config && tool === "skinfix" && (
        <SkinFixTool config={config} previewMode={previewMode} />
      )}
    </AppShell>
  );
}
