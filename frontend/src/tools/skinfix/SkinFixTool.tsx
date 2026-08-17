import { useCallback, useRef, useState } from "react";
import type {
  AppConfig,
  SelectedImage,
  SkinFixMode,
  SkinFixResult,
  SkinFixStrength,
} from "../../lib/types";
import * as api from "../../lib/api";
import { ApiError } from "../../lib/api";
import { isAcceptedFile, loadSelectedImage, revokeSelected } from "../../lib/images";
import { formatDimensions } from "../../lib/format";
import { Dropzone } from "../upscaler/Dropzone";
import { BeforeAfterSlider } from "../../components/BeforeAfterSlider";
import { MaskCanvas, type SkinMaskHandle } from "./MaskCanvas";

interface Props {
  config: AppConfig;
  previewMode?: boolean;
}

export function SkinFixTool({ config, previewMode = false }: Props) {
  const [image, setImage] = useState<SelectedImage | null>(null);
  const [mode, setMode] = useState<SkinFixMode>("masked");
  const [strength, setStrength] = useState<SkinFixStrength>("standard");
  const [brushSize, setBrushSize] = useState(40);
  const [brushMode, setBrushMode] = useState<"brush" | "eraser">("brush");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SkinFixResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const maskRef = useRef<SkinMaskHandle>(null);
  const imageRef = useRef<SelectedImage | null>(null);
  imageRef.current = image;

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 3600);
  }, []);

  const addImage = useCallback(
    async (files: File[]) => {
      const file = files.find(isAcceptedFile);
      if (!file) {
        showToast("Only JPG, PNG or WEBP images are supported.");
        return;
      }
      try {
        const loaded = await loadSelectedImage(file);
        if (imageRef.current) revokeSelected(imageRef.current);
        setImage(loaded);
        setResult(null);
        setError(null);
      } catch {
        showToast(`Couldn't read ${file.name}.`);
      }
    },
    [showToast],
  );

  const fixSkin = useCallback(async () => {
    if (!image || running || previewMode) return;
    setError(null);

    let mask: Blob | null = null;
    if (mode === "masked") {
      mask = (await maskRef.current?.exportMask()) ?? null;
      if (!mask) {
        setError(
          "Paint over the skin you want to fix, or switch to full-image fix.",
        );
        return;
      }
    }

    setRunning(true);
    try {
      const res = await api.skinFix(image.file, mask, mode, strength);
      setResult(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't fix this image.");
    } finally {
      setRunning(false);
    }
  }, [image, running, previewMode, mode, strength]);

  const startOver = useCallback(() => {
    if (imageRef.current) revokeSelected(imageRef.current);
    setImage(null);
    setResult(null);
    setError(null);
  }, []);

  const backToEdit = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  const clearMask = () => maskRef.current?.clear();

  return (
    <>
      <header className="qw-toolhead">
        <div className="qw-eyebrow">QWEEN AI Tools</div>
        <h1 className="qw-display qw-toolhead__title">Skin Fix</h1>
        <p className="qw-toolhead__lede">
          Repair skin flakiness, dryness and peeling while preserving natural
          pores, texture, lighting and identity.
        </p>
      </header>

      {!previewMode && !config.openai_configured && (
        <div className="qw-banner qw-banner--warn">
          <span>
            <b>OPENAI_API_KEY is not configured on the backend.</b> Skin Fix will
            not run until a key is added.
          </span>
        </div>
      )}

      {error && (
        <div className="qw-banner qw-banner--error">
          <span style={{ whiteSpace: "pre-line" }}>{error}</span>
        </div>
      )}

      {/* Upload */}
      {!image && (
        <div className="qw-section">
          <Dropzone onFiles={addImage} />
        </div>
      )}

      {/* Edit */}
      {image && !result && (
        <div className="qw-section qw-skin-layout">
          <div className="qw-skin-stage">
            <MaskCanvas
              ref={maskRef}
              imageUrl={image.previewUrl}
              naturalWidth={image.width}
              naturalHeight={image.height}
              brushSize={brushSize}
              brushMode={brushMode}
              active={mode === "masked"}
            />
            <div className="qw-skin-stage__meta">
              {image.file.name} · {formatDimensions(image.width, image.height)}
            </div>
          </div>

          <div className="qw-skin-panel">
            <div className="qw-field">
              <span className="qw-field__label">Fix mode</span>
              <div className="qw-seg qw-seg--block">
                <button
                  className={mode === "masked" ? "is-on" : ""}
                  onClick={() => setMode("masked")}
                >
                  Masked fix
                </button>
                <button
                  className={mode === "full" ? "is-on" : ""}
                  onClick={() => setMode("full")}
                >
                  Full-image fix
                </button>
              </div>
              <span className="qw-preview-name">
                {mode === "masked"
                  ? "Fixes only the area you paint below."
                  : "Fixes all skin in the image."}
              </span>
            </div>

            {mode === "masked" && (
              <div className="qw-field">
                <span className="qw-field__label">Brush · {brushSize}px</span>
                <input
                  className="qw-range"
                  type="range"
                  min={10}
                  max={80}
                  step={2}
                  value={brushSize}
                  onChange={(e) => setBrushSize(parseInt(e.target.value, 10))}
                />
                <div className="qw-seg qw-seg--block" style={{ marginTop: 10 }}>
                  <button
                    className={brushMode === "brush" ? "is-on" : ""}
                    onClick={() => setBrushMode("brush")}
                  >
                    Brush
                  </button>
                  <button
                    className={brushMode === "eraser" ? "is-on" : ""}
                    onClick={() => setBrushMode("eraser")}
                  >
                    Eraser
                  </button>
                  <button onClick={clearMask}>Clear</button>
                </div>
                <span className="qw-preview-name">
                  Paint over the skin to fix — everything else is preserved
                  exactly.
                </span>
              </div>
            )}

            <div className="qw-field">
              <span className="qw-field__label">Fix strength</span>
              <div className="qw-seg qw-seg--block">
                <button
                  className={strength === "subtle" ? "is-on" : ""}
                  onClick={() => setStrength("subtle")}
                >
                  Subtle
                </button>
                <button
                  className={strength === "standard" ? "is-on" : ""}
                  onClick={() => setStrength("standard")}
                >
                  Standard
                </button>
              </div>
            </div>

            <div className="qw-skin-actions">
              <button className="qw-btn qw-btn--ghost" onClick={startOver}>
                Change image
              </button>
              <button
                className="qw-btn qw-btn--gold qw-btn--block"
                onClick={fixSkin}
                disabled={running || previewMode}
                title={previewMode ? "Connect a backend to run Skin Fix" : undefined}
              >
                {running ? "Fixing…" : "Fix skin"}
              </button>
            </div>
            {running && (
              <div className="qw-preview-name" style={{ textAlign: "center" }}>
                This can take up to a minute.
              </div>
            )}
          </div>
        </div>
      )}

      {/* Result */}
      {image && result && (
        <div className="qw-section">
          <div className="qw-results-head">
            <div className="qw-eyebrow">Complete</div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <button className="qw-btn qw-btn--ghost qw-btn--sm" onClick={backToEdit}>
                Adjust &amp; re-run
              </button>
              <a
                className="qw-btn qw-btn--sm"
                href={api.skinFixDownloadUrl(result.result_id)}
                download={result.output_filename}
              >
                Download
              </a>
            </div>
          </div>

          <div className="qw-result">
            <BeforeAfterSlider
              beforeSrc={image.previewUrl}
              afterSrc={api.skinFixPreviewUrl(result.result_id)}
            />
          </div>

          <div className="qw-actions-row">
            <button className="qw-btn qw-btn--ghost" onClick={startOver}>
              Fix another image
            </button>
          </div>
        </div>
      )}

      {toast && <div className="qw-toast">{toast}</div>}
    </>
  );
}
