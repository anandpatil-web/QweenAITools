import type { SelectedImage } from "../../lib/types";
import { formatDimensions, formatMegapixels } from "../../lib/format";

interface Props {
  images: SelectedImage[];
  onRemove: (localId: string) => void;
}

export function ImageGrid({ images, onRemove }: Props) {
  return (
    <div className="qw-grid">
      {images.map((img) => {
        const mp = (img.width * img.height) / 1_000_000;
        return (
          <div className="qw-card" key={img.localId}>
            <div className="qw-thumb">
              <img src={img.thumbUrl} alt={img.file.name} loading="lazy" />
              <button
                className="qw-thumb__remove"
                title="Remove"
                aria-label={`Remove ${img.file.name}`}
                onClick={() => onRemove(img.localId)}
              >
                ×
              </button>
            </div>
            <div className="qw-card__body">
              <div className="qw-card__name" title={img.file.name}>
                {img.file.name}
              </div>
              <div className="qw-card__meta">
                <span>{formatDimensions(img.width, img.height)}</span>
                <span>·</span>
                <span>{formatMegapixels(mp)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
