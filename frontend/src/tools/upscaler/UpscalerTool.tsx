import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AppConfig,
  ImageState,
  JobResponse,
  SelectedImage,
  SseEvent,
} from "../../lib/types";
import * as api from "../../lib/api";
import { ApiError } from "../../lib/api";
import { formatInr, formatUsd } from "../../lib/format";
import { isAcceptedFile, loadSelectedImage, revokeSelected } from "../../lib/images";
import { Dropzone } from "./Dropzone";
import { ImageGrid } from "./ImageGrid";
import { SettingsBar } from "./SettingsBar";
import { JobView } from "./JobView";

type Phase = "select" | "job";

interface Props {
  config: AppConfig;
  previewMode?: boolean;
}

export function UpscalerTool({ config, previewMode = false }: Props) {
  const [phase, setPhase] = useState<Phase>("select");
  const [selected, setSelected] = useState<SelectedImage[]>([]);
  const [scale, setScale] = useState(config.default_scale_factor);
  const [creativity, setCreativity] = useState(config.creativity_default);
  const [suffix, setSuffix] = useState(config.default_suffix ?? "");
  const [concurrency, setConcurrency] = useState(config.default_concurrency);

  const [running, setRunning] = useState(false);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [finished, setFinished] = useState(false);
  const [localByScanId, setLocalByScanId] = useState<Record<string, SelectedImage>>({});
  const [retrying, setRetrying] = useState<Set<string>>(new Set());
  const [retryingAll, setRetryingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 3600);
  }, []);

  // --- selection ---------------------------------------------------------

  const addFiles = useCallback(
    async (files: File[]) => {
      const accepted = files.filter(isAcceptedFile);
      const rejected = files.length - accepted.length;
      if (rejected > 0) {
        showToast(
          `${rejected} file${rejected > 1 ? "s were" : " was"} skipped — only JPG, PNG or WEBP are supported.`,
        );
      }
      const loaded: SelectedImage[] = [];
      for (const file of accepted) {
        try {
          loaded.push(await loadSelectedImage(file));
        } catch {
          showToast(`Couldn't read ${file.name}.`);
        }
      }
      if (loaded.length) setSelected((prev) => [...prev, ...loaded]);
    },
    [showToast],
  );

  const removeImage = useCallback((localId: string) => {
    setSelected((prev) => {
      const target = prev.find((p) => p.localId === localId);
      if (target) revokeSelected(target);
      return prev.filter((p) => p.localId !== localId);
    });
  }, []);

  // --- SSE ---------------------------------------------------------------

  const applyEvent = useCallback((evt: SseEvent) => {
    setJob((prev) => {
      if (!prev) return prev;
      if (evt.type === "snapshot") {
        const map = new Map(prev.images.map((i) => [i.id, i]));
        for (const s of evt.images) {
          const existing = map.get(s.image_id);
          if (existing) {
            map.set(s.image_id, {
              ...existing,
              status: s.status,
              result_id: s.result_id ?? existing.result_id,
              output_filename: s.output_filename ?? existing.output_filename,
              error: s.error ?? existing.error,
            });
          }
        }
        return {
          ...prev,
          images: prev.images.map((i) => map.get(i.id) ?? i),
          completed: evt.completed,
          succeeded: evt.succeeded,
          failed: evt.failed,
          timed_out: evt.timed_out,
        };
      }
      if (evt.type === "image_status") {
        return {
          ...prev,
          images: prev.images.map((i): ImageState =>
            i.id === evt.image_id
              ? {
                  ...i,
                  status: evt.status,
                  result_id: evt.result_id ?? i.result_id,
                  output_filename: evt.output_filename ?? i.output_filename,
                  error:
                    evt.error ??
                    (evt.status === "failed" || evt.status === "timeout"
                      ? i.error
                      : null),
                }
              : i,
          ),
        };
      }
      if (evt.type === "job_progress") {
        return { ...prev, completed: evt.completed, total: evt.total };
      }
      if (evt.type === "job_complete") {
        return {
          ...prev,
          completed: evt.completed,
          succeeded: evt.succeeded,
          failed: evt.failed,
          timed_out: evt.timed_out,
        };
      }
      return prev;
    });
  }, []);

  const connectStream = useCallback(
    (jobId: string) => {
      esRef.current?.close();
      const es = new EventSource(api.eventsUrl(jobId));
      esRef.current = es;
      es.onmessage = (e) => {
        try {
          const evt: SseEvent = JSON.parse(e.data);
          applyEvent(evt);
          if (evt.type === "job_complete") {
            setFinished(true);
            setRetrying(new Set());
            setRetryingAll(false);
            es.close();
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      es.onerror = () => {
        es.close();
      };
    },
    [applyEvent],
  );

  // --- run (scan + start, no separate estimate step) ---------------------

  const upscaleNow = useCallback(async () => {
    if (!selected.length || running || previewMode) return;
    setRunning(true);
    setError(null);
    try {
      // Validate + upload happens here; we just don't show a separate screen.
      const result = await api.scan(selected, scale, creativity, suffix, "jpeg");

      if (result.errors.length > 0) {
        showToast(
          `${result.errors.length} image${result.errors.length > 1 ? "s" : ""} skipped (unsupported or unreadable).`,
        );
      }
      if (result.total_images === 0) {
        setError("None of the selected images could be used. Please check the files.");
        return;
      }

      // Map scanned ids back to their local selection (order preserved,
      // rejected files skipped) so we can show the original as "before".
      const byScanId: Record<string, SelectedImage> = {};
      let pointer = 0;
      for (const scanned of result.images) {
        while (
          pointer < selected.length &&
          selected[pointer].file.name !== scanned.filename
        ) {
          pointer += 1;
        }
        if (pointer < selected.length) {
          byScanId[scanned.id] = selected[pointer];
          pointer += 1;
        }
      }
      setLocalByScanId(byScanId);

      const started = await api.startJob(result.scan_id, concurrency);
      setJob(started);
      setFinished(false);
      setPhase("job");
      connectStream(started.job_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't start upscaling.");
    } finally {
      setRunning(false);
    }
  }, [selected, running, previewMode, scale, creativity, suffix, concurrency, connectStream, showToast]);

  // --- retry / reset -----------------------------------------------------

  const doRetry = useCallback(
    async (imageIds?: string[]) => {
      if (!job) return;
      if (imageIds) setRetrying(new Set(imageIds));
      else setRetryingAll(true);
      try {
        const updated = await api.retry(job.job_id, imageIds);
        setJob((prev) => (prev ? { ...prev, ...updated } : updated));
        setFinished(false);
        connectStream(job.job_id);
      } catch (e) {
        showToast(e instanceof ApiError ? e.message : "Retry failed.");
        setRetrying(new Set());
        setRetryingAll(false);
      }
    },
    [job, connectStream, showToast],
  );

  const startOver = useCallback(() => {
    esRef.current?.close();
    selectedRef.current.forEach(revokeSelected);
    setSelected([]);
    setJob(null);
    setFinished(false);
    setLocalByScanId({});
    setRetrying(new Set());
    setRetryingAll(false);
    setError(null);
    setPhase("select");
  }, []);

  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, []);

  const sampleName = selected[0]?.file.name ?? "";
  // Cost = $/MP × output megapixels, where output = input × scale². Computed
  // live from each image's real dimensions (instant, no server round-trip).
  const totalUsd = selected.reduce(
    (sum, img) =>
      sum + config.usd_per_megapixel * ((img.width * img.height * scale * scale) / 1_000_000),
    0,
  );
  const totalInr = totalUsd * config.usd_to_inr;

  // --- render ------------------------------------------------------------

  return (
    <>
      <header className="qw-toolhead">
        <div className="qw-eyebrow">QWEEN AI Tools</div>
        <h1 className="qw-display qw-toolhead__title">Image Upscaler</h1>
        <p className="qw-toolhead__lede">
          Enhance and upscale your jewellery imagery while preserving every
          diamond edge, gemstone facet and fine metal texture.
        </p>
      </header>

      {!previewMode && !config.fal_configured && (
        <div className="qw-banner qw-banner--warn">
          <span>
            <b>FAL_KEY is not configured on the backend.</b> Upscaling will fail
            until a key is added.
          </span>
        </div>
      )}

      {error && (
        <div className="qw-banner qw-banner--error">
          <span style={{ whiteSpace: "pre-line" }}>{error}</span>
        </div>
      )}

      {phase === "select" && (
        <div className="qw-section">
          {selected.length === 0 ? (
            <Dropzone onFiles={addFiles} />
          ) : (
            <>
              <div className="qw-bar">
                <div className="qw-count">
                  {selected.length}
                  <small>{selected.length === 1 ? "image" : "images"}</small>
                </div>
                <Dropzone onFiles={addFiles} compact />
              </div>

              <SettingsBar
                config={config}
                scale={scale}
                creativity={creativity}
                suffix={suffix}
                concurrency={concurrency}
                sampleName={sampleName}
                onScale={setScale}
                onCreativity={setCreativity}
                onSuffix={setSuffix}
                onConcurrency={setConcurrency}
              />

              <ImageGrid images={selected} onRemove={removeImage} />

              <div className="qw-runbar">
                <button className="qw-btn qw-btn--ghost" onClick={startOver}>
                  Clear all
                </button>
                <div className="qw-spacer" />
                <div className="qw-runcost">
                  <span className="qw-runcost__label">Cost</span>
                  <b className="qw-runcost__usd">{formatUsd(totalUsd)}</b>
                  <span className="qw-runcost__inr">≈ {formatInr(totalInr)}</span>
                </div>
                <button
                  className="qw-btn qw-btn--gold"
                  onClick={upscaleNow}
                  disabled={running || selected.length === 0 || previewMode}
                  title={
                    previewMode ? "Connect a backend to upscale" : undefined
                  }
                >
                  {running
                    ? "Starting…"
                    : `Upscale ${selected.length} image${selected.length > 1 ? "s" : ""}`}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {phase === "job" && job && (
        <JobView
          job={job}
          finished={finished}
          localById={localByScanId}
          retrying={retrying}
          retryingAll={retryingAll}
          onRetry={(id) => doRetry([id])}
          onRetryAll={() => doRetry(undefined)}
          onStartOver={startOver}
        />
      )}

      {toast && <div className="qw-toast">{toast}</div>}
    </>
  );
}
