import type { JobResponse, SelectedImage } from "../../lib/types";
import { downloadAllUrl } from "../../lib/api";
import { JobImageCard } from "./JobImageCard";

interface Props {
  job: JobResponse;
  finished: boolean;
  localById: Record<string, SelectedImage | undefined>;
  retrying: Set<string>;
  retryingAll: boolean;
  onRetry: (imageId: string) => void;
  onRetryAll: () => void;
  onStartOver: () => void;
}

export function JobView({
  job,
  finished,
  localById,
  retrying,
  retryingAll,
  onRetry,
  onRetryAll,
  onStartOver,
}: Props) {
  const images = job.images;
  const inProgress = images.filter(
    (i) => !["done", "failed", "timeout"].includes(i.status),
  );
  const done = images.filter((i) => i.status === "done");
  const failed = images.filter(
    (i) => i.status === "failed" || i.status === "timeout",
  );

  const active = images.filter((i) =>
    ["uploading", "processing", "downloading"].includes(i.status),
  ).length;
  const queued = images.filter((i) => i.status === "queued").length;
  const pct = job.total ? Math.round((job.completed / job.total) * 100) : 0;

  const succeeded = done.length;
  const anyFailed = failed.length > 0;

  return (
    <div className="qw-section">
      <div className="qw-progresshead">
        <div className="qw-eyebrow">{finished ? "Complete" : "Upscaling"}</div>
        <div className="qw-progresshead__count">
          {job.completed} / {job.total} complete
        </div>
        <div className="qw-progressbar">
          <div className="qw-progressbar__fill" style={{ width: `${pct}%` }} />
        </div>
        <div className="qw-progresstally">
          <span>
            <b>{succeeded}</b> done
          </span>
          {!finished && active > 0 && (
            <span>
              <b>{active}</b> processing
            </span>
          )}
          {!finished && queued > 0 && (
            <span>
              <b>{queued}</b> queued
            </span>
          )}
          {anyFailed && (
            <span>
              <b>{failed.length}</b> failed
            </span>
          )}
        </div>
      </div>

      {(finished || succeeded > 0) && (
        <div className="qw-results-head">
          <div className="qw-results-summary">
            <span>
              <b>{succeeded}</b> successful
            </span>
            {anyFailed && (
              <span>
                <b>{failed.length}</b> unsuccessful
              </span>
            )}
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {anyFailed && finished && (
              <button
                className="qw-btn qw-btn--ghost qw-btn--sm"
                onClick={onRetryAll}
                disabled={retryingAll}
              >
                {retryingAll ? "Retrying…" : "Retry Failed"}
              </button>
            )}
            {succeeded > 1 && (
              <a className="qw-btn qw-btn--sm" href={downloadAllUrl(job.job_id)}>
                Download All
              </a>
            )}
          </div>
        </div>
      )}

      {inProgress.length > 0 && (
        <div className="qw-grid" style={{ marginBottom: 28 }}>
          {inProgress.map((img) => (
            <JobImageCard
              key={img.id}
              image={img}
              thumbSrc={localById[img.id]?.thumbUrl}
              retrying={false}
              onRetry={onRetry}
            />
          ))}
        </div>
      )}

      {done.map((img) => (
        <JobImageCard
          key={img.id}
          image={img}
          beforeSrc={localById[img.id]?.previewUrl}
          thumbSrc={localById[img.id]?.thumbUrl}
          retrying={false}
          onRetry={onRetry}
        />
      ))}

      {failed.map((img) => (
        <JobImageCard
          key={img.id}
          image={img}
          retrying={retrying.has(img.id) || retryingAll}
          onRetry={onRetry}
        />
      ))}

      {finished && (
        <div className="qw-actions-row">
          <button className="qw-btn qw-btn--ghost" onClick={onStartOver}>
            Start over
          </button>
        </div>
      )}
    </div>
  );
}
