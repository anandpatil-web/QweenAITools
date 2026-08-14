import { useCallback, useRef, useState } from "react";

interface Props {
  beforeSrc: string;
  afterSrc: string;
  beforeLabel?: string;
  afterLabel?: string;
}

/** Interactive before/after comparison. Drag anywhere on the image, or use the
 *  arrow keys when focused, to inspect fine jewellery detail. */
export function BeforeAfterSlider({
  beforeSrc,
  afterSrc,
  beforeLabel = "Before",
  afterLabel = "After",
}: Props) {
  const [split, setSplit] = useState(50);
  const ref = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const setFromClientX = useCallback((clientX: number) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setSplit(Math.max(0, Math.min(100, pct)));
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    setFromClientX(e.clientX);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    setFromClientX(e.clientX);
  };
  const onPointerUp = () => {
    dragging.current = false;
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowLeft") setSplit((s) => Math.max(0, s - 2));
    if (e.key === "ArrowRight") setSplit((s) => Math.min(100, s + 2));
  };

  return (
    <div
      ref={ref}
      className="qw-ba"
      style={{ ["--split" as string]: `${split}%` }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onKeyDown={onKeyDown}
      tabIndex={0}
      role="slider"
      aria-label="Before and after comparison"
      aria-valuenow={Math.round(split)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {/* After fills the frame; before is clipped on top from the left. */}
      <img className="qw-ba__after" src={afterSrc} alt={afterLabel} draggable={false} />
      <div className="qw-ba__before-wrap">
        <img src={beforeSrc} alt={beforeLabel} draggable={false} />
      </div>
      <span className="qw-ba__tag qw-ba__tag--before">{beforeLabel}</span>
      <span className="qw-ba__tag qw-ba__tag--after">{afterLabel}</span>
      <div className="qw-ba__handle" />
      <div className="qw-ba__knob" aria-hidden>
        ⟺
      </div>
    </div>
  );
}
