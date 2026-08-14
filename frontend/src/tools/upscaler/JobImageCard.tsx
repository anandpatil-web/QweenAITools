import type { ImageState } from "../../lib/types";
import { formatDimensions } from "../../lib/format";
import { resultDownloadUrl, resultPreviewUrl } from "../../lib/api";
import { BeforeAfterSlider } from "../../components/BeforeAfterSlider";
import { StatusPill } from "./StatusPill";

interface Props {
  image: ImageState;
  beforeSrc?: string;
  thumbSrc?: string;
  retrying: boolean;
  onRetry: (imageId: string) => void;
}

export function JobImageCard({
  image,
  beforeSrc,
  thumbSrc,
  retrying,
  onRetry,
}: Props) {
  const isDone = image.status === "done" && image.result_id;
  const isFailed = image.status === "failed" || image.status === "timeout";

  if (isFailed) {
    return (
      <div className="qw-result qw-result--failed">
        <div className="qw-failbox">
          <div>
            <div className="qw-result__name" style={{ fontSize: 18 }}>
              {image.filename}
            </div>
            <StatusPill status={image.status} />
            <div className="qw-failbox__msg" style={{ marginTop: 10 }}>
              {image.error ||
                (image.status === "timeout"
                  ? "This image took too long to process."
                  : "fal.ai returned an error.")}
            </div>
          </div>
          <button
            className="qw-btn qw-btn--sm"
            onClick={() => onRetry(image.id)}
            disabled={retrying}
          >
            {retrying ? "Retrying…" : "Retry"}
          </button>
        </div>
      </div>
    );
  }

  if (isDone) {
    const afterPreview = resultPreviewUrl(image.result_id!);
    return (
      <div className="qw-result">
        <div className="qw-result__body">
          {beforeSrc ? (
            <BeforeAfterSlider beforeSrc={beforeSrc} afterSrc={afterPreview} />
          ) : (
            <div className="qw-ba">
              <img className="qw-ba__after" src={afterPreview} alt="Upscaled" />
              <span className="qw-ba__tag qw-ba__tag--after">After</span>
            </div>
          )}
          <div className="qw-result__aside">
            <div className="qw-result__name">{image.output_filename || image.filename}</div>
            <div>
              <div className="qw-dim">
                <span>Before</span>
                <b>{formatDimensions(image.width, image.height)}</b>
              </div>
              <div className="qw-dim">
                <span>After</span>
                <b>{formatDimensions(image.output_width, image.output_height)}</b>
              </div>
              {image.duration_seconds != null && (
                <div className="qw-dim">
                  <span>Time</span>
                  <b>{image.duration_seconds.toFixed(1)}s</b>
                </div>
              )}
            </div>
            <StatusPill status={image.status} />
            <div className="qw-result__actions">
              <a
                className="qw-btn qw-btn--sm"
                href={resultDownloadUrl(image.result_id!)}
                download={image.output_filename || undefined}
              >
                Download
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // In-progress card.
  return (
    <div className="qw-card" style={{ maxWidth: 260 }}>
      <div className="qw-thumb">
        {thumbSrc ? (
          <img src={thumbSrc} alt={image.filename} />
        ) : (
          <div style={{ width: "100%", height: "100%" }} />
        )}
      </div>
      <div className="qw-card__body">
        <div className="qw-card__name" title={image.filename}>
          {image.filename}
        </div>
        <div style={{ marginTop: 10 }}>
          <StatusPill status={image.status} />
        </div>
      </div>
    </div>
  );
}
