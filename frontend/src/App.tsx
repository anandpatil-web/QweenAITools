import { useEffect, useState } from "react";
import { AppShell } from "./components/AppShell";
import { UpscalerTool } from "./tools/upscaler/UpscalerTool";
import { fetchConfig } from "./lib/api";
import type { AppConfig } from "./lib/types";

export function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchConfig()
      .then(setConfig)
      .catch(() =>
        setError(
          "Couldn't reach the QWEEN backend. Make sure it is running on port 8000.",
        ),
      );
  }, []);

  return (
    <AppShell>
      {error && <div className="qw-banner qw-banner--error">{error}</div>}
      {!error && !config && (
        <div className="qw-eyebrow" style={{ padding: "40px 0" }}>
          Loading…
        </div>
      )}
      {config && <UpscalerTool config={config} />}
    </AppShell>
  );
}
