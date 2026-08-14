import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  AppConfig,
  ImageState,
  JobResponse,
  ScanResponse,
  ScannedImage,
  SelectedImage,
  SseEvent,
} from "../../lib/types";
import * as api from "../../lib/api";
import { ApiError } from "../../lib/api";
import { isAcceptedFile, loadSelectedImage, revokeSelected } from "../../lib/images";
import { Dropzone } from "./Dropzone";
import { ImageGrid } from "./ImageGrid";
import { SettingsBar } from "./SettingsBar";
import { EstimatePanel } from "./EstimatePanel";
import { JobView } from "./JobView";

type Phase = "select" | "estimate" | "job";

interface Props {
  config: AppConfig;
  previewMode?: boolean;
}

export function UpscalerTool({ config, previewMode = false }: Props) {
  const [phase, setPhase] = useState<Phase>("select");
  const [selected, setSelected] = useState<SelectedImage[]>([]);
  const [scale, setScale] = useState(config.default_scale_factor);
  const [suffix, setSuffix] = useState(config.default_suffix ?? "");
  const [concurrency, setConcurrency] = useState(config.default_concurrency);

  const [scanning, setScanning] = useState(false);
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [estimatesByLocal, setEstimatesByLocal] = useState<Record<string, ScannedImage>>({});
  const [localByScanId, setLocalByScanId] = useState<Record<string, SelectedImage>>({});
  const [error, setError] = useState<string | null>(null);

  const [starting, setStarting] = useState(false);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [finished, setFinished] = useState(false);
  const [retrying, setRetrying] = useState<Set<string>>(new Set());
  const [retryingAll, setRetryingAll] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 3200);
  }, []);

  // --- selection ---------------------------------------------------------

  const invalidateScan = useCallback(() => {
    setScan(null);
    setEstimatesByLocal({});
    setLocalByScanId({});
    if (phase === "estimate") setPhase("select");
  }, [phase]);

  const addFiles = useCallback(
    async (files: File[]) => {
      const accepted = files.filter(isAcceptedFile);
      const rejected = files.length - accepted.length;
      if (rejected > 0) {
        showToast(
          `${rejected} file${rejected > 1 ? "s were" : " was"} skipped — only JPG, PNG or WEBP are supported.`,
        );
      }
      invalidateScan();
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
    [invalidateScan, showToast],
  );

  const removeImage = useCallback(
    (localId: string) => {
      setSelected((prev) => {
        const target = prev.find((p) => p.localId === localId);
        if (target) revokeSelected(target);
        return prev.filter((p) => p.localId !== localId);
      });
      invalidateScan();
    },
    [invalidateScan],
  );

  // --- scan / estimate ---------------------------------------------------

  const runScan = useCallback(async () => {
    if (!selected.length) return;
    setScanning(true);
    setError(null);
    try {
      const result = await api.scan(selected, scale, suffix, "jpeg");
      // Map scanned ids back to their local selection (order preserved,
      // rejected files skipped) so we can show the original as "before".
      const byLocal: Record<string, ScannedImage> = {};
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
          byLocal[selected[pointer].localId] = scanned;
          byScanId[scanned.id] = selected[pointer];
          pointer += 1;
        }
      }
      setEstimatesByLocal(byLocal);
      setLocalByScanId(byScanId);
      setScan(result);
      if (result.total_images > 0) {
        setPhase("estimate");
      } else {
        showToast("No usable images were found. Please check the files.");
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't scan the images.");
    } finally {
      setScanning(false);
    }
  }, [selected, scale, suffix, showToast]);

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
                  error: evt.error ?? (evt.status === "failed" || evt.status === "timeout" ? i.error : null),
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
        // The stream closes itself after completion; only treat unexpected
        // drops as errors by falling back to a one-off poll.
        es.close();
      };
    },
    [applyEvent],
  );

  // --- run / retry -------------------------------------------------------

  const confirmRun = useCallback(async () => {
    if (!scan) return;
    setStarting(true);
    setError(null);
    try {
      const started = await api.startJob(scan.scan_id, concurrency);
      setJob(started);
      setFinished(false);
      setPhase("job");
      connectStream(started.job_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't start processing.");
    } finally {
      setStarting(false);
    }
  }, [scan, concurrency, connectStream]);

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
    setScan(null);
    setEstimatesByLocal({});
    setLocalByScanId({});
    setJob(null);
    setFinished(false);
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

  const localByJobImageId = useMemo(() => localByScanId, [localByScanId]);
  const sampleName = selected[0]?.file.name ?? "";

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
            <b>FAL_KEY is not configured on the backend.</b> You can select
            images and see cost estimates, but processing will fail until a key
            is added to <code>backend/.env</code>.
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
                suffix={suffix}
                concurrency={concurrency}
                sampleName={sampleName}
                onScale={(v) => {
                  setScale(v);
                  invalidateScan();
                }}
                onSuffix={(v) => {
                  setSuffix(v);
                  invalidateScan();
                }}
                onConcurrency={setConcurrency}
              />

              {scan && scan.errors.length > 0 && (
                <div className="qw-scan-errors">
                  <div className="qw-scan-errors__title">
                    {scan.errors.length} image{scan.errors.length > 1 ? "s" : ""} skipped
                  </div>
                  <ul>
                    {scan.errors.map((er, idx) => (
                      <li key={idx}>
                        <b>{er.filename}</b> — {er.error}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <ImageGrid
                images={selected}
                estimates={estimatesByLocal}
                onRemove={removeImage}
              />

              <div className="qw-actions-row">
                <button
                  className="qw-btn qw-btn--ghost"
                  onClick={startOver}
                >
                  Clear all
                </button>
                <div className="qw-spacer" />
                <button
                  className="qw-btn"
                  onClick={runScan}
                  disabled={scanning || selected.length === 0 || previewMode}
                  title={
                    previewMode
                      ? "Connect a backend to scan and upscale"
                      : undefined
                  }
                >
                  {scanning ? "Scanning…" : "Scan & Estimate"}
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {phase === "estimate" && scan && (
        <EstimatePanel
          scan={scan}
          busy={starting}
          onBack={() => setPhase("select")}
          onConfirm={confirmRun}
        />
      )}

      {phase === "job" && job && (
        <JobView
          job={job}
          finished={finished}
          localById={localByJobImageId}
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
