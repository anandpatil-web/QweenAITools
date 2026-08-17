import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";

export interface SkinMaskHandle {
  /** PNG blob: black = preserved, transparent = editable. Null if nothing painted. */
  exportMask: () => Promise<Blob | null>;
  clear: () => void;
  hasPaint: () => boolean;
}

interface Props {
  imageUrl: string;
  naturalWidth: number;
  naturalHeight: number;
  brushSize: number; // display pixels (diameter)
  brushMode: "brush" | "eraser";
  active: boolean; // masked mode → brushing enabled
}

const PAINT_MAX_EDGE = 1280;
const PAINT_COLOR = "rgba(219, 68, 55, 0.45)";

export const MaskCanvas = forwardRef<SkinMaskHandle, Props>(function MaskCanvas(
  { imageUrl, naturalWidth, naturalHeight, brushSize, brushMode, active },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const last = useRef<{ x: number; y: number } | null>(null);

  // Size the paint canvas to the image aspect, capped for performance.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !naturalWidth || !naturalHeight) return;
    let w = naturalWidth;
    let h = naturalHeight;
    const longEdge = Math.max(w, h);
    if (longEdge > PAINT_MAX_EDGE) {
      const s = PAINT_MAX_EDGE / longEdge;
      w = Math.round(w * s);
      h = Math.round(h * s);
    }
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    ctx?.clearRect(0, 0, w, h);
  }, [imageUrl, naturalWidth, naturalHeight]);

  const toCanvasPoint = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (clientX - rect.left) * scaleX,
      y: (clientY - rect.top) * scaleY,
      radius: (brushSize / 2) * scaleX,
    };
  };

  const stroke = (from: { x: number; y: number } | null, to: { x: number; y: number }, radius: number) => {
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;
    ctx.globalCompositeOperation = brushMode === "eraser" ? "destination-out" : "source-over";
    ctx.fillStyle = PAINT_COLOR;
    ctx.strokeStyle = PAINT_COLOR;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.lineWidth = radius * 2;
    ctx.beginPath();
    ctx.arc(to.x, to.y, radius, 0, Math.PI * 2);
    ctx.fill();
    if (from) {
      ctx.beginPath();
      ctx.moveTo(from.x, from.y);
      ctx.lineTo(to.x, to.y);
      ctx.stroke();
    }
    ctx.globalCompositeOperation = "source-over";
  };

  const onPointerDown = (e: React.PointerEvent) => {
    if (!active) return;
    drawing.current = true;
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    const p = toCanvasPoint(e.clientX, e.clientY);
    stroke(null, p, p.radius);
    last.current = { x: p.x, y: p.y };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!active || !drawing.current) return;
    const p = toCanvasPoint(e.clientX, e.clientY);
    stroke(last.current, p, p.radius);
    last.current = { x: p.x, y: p.y };
  };
  const onPointerUp = () => {
    drawing.current = false;
    last.current = null;
  };

  useImperativeHandle(ref, () => ({
    clear() {
      const c = canvasRef.current;
      c?.getContext("2d")?.clearRect(0, 0, c.width, c.height);
    },
    hasPaint() {
      const c = canvasRef.current;
      if (!c) return false;
      const SMALL = 128;
      const tmp = document.createElement("canvas");
      tmp.width = SMALL;
      tmp.height = SMALL;
      const t = tmp.getContext("2d");
      if (!t) return false;
      t.drawImage(c, 0, 0, SMALL, SMALL);
      const data = t.getImageData(0, 0, SMALL, SMALL).data;
      for (let i = 3; i < data.length; i += 4) if (data[i] > 8) return true;
      return false;
    },
    async exportMask() {
      const paint = canvasRef.current;
      if (!paint) return null;
      // Reuse hasPaint check inline
      const SMALL = 128;
      const tmp = document.createElement("canvas");
      tmp.width = SMALL;
      tmp.height = SMALL;
      const t = tmp.getContext("2d");
      if (t) {
        t.drawImage(paint, 0, 0, SMALL, SMALL);
        const d = t.getImageData(0, 0, SMALL, SMALL).data;
        let painted = false;
        for (let i = 3; i < d.length; i += 4) if (d[i] > 8) { painted = true; break; }
        if (!painted) return null;
      }
      const mask = document.createElement("canvas");
      mask.width = paint.width;
      mask.height = paint.height;
      const ctx = mask.getContext("2d");
      if (!ctx) return null;
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, mask.width, mask.height);
      ctx.globalCompositeOperation = "destination-out";
      ctx.drawImage(paint, 0, 0);
      ctx.globalCompositeOperation = "source-over";
      return await new Promise<Blob | null>((resolve) =>
        mask.toBlob((b) => resolve(b), "image/png"),
      );
    },
  }));

  return (
    <div className="qw-skin-canvas">
      <img src={imageUrl} alt="Working image" draggable={false} />
      <canvas
        ref={canvasRef}
        className={`qw-skin-paint${active ? " is-active" : ""}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      />
    </div>
  );
});
