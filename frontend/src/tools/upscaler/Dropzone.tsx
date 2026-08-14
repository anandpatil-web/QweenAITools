import { useRef, useState } from "react";

interface Props {
  onFiles: (files: File[]) => void;
  compact?: boolean;
}

export function Dropzone({ onFiles, compact }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  const pick = () => inputRef.current?.click();

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const files = Array.from(e.dataTransfer.files || []);
    if (files.length) onFiles(files);
  };

  return (
    <div
      className={`qw-dropzone${drag ? " is-drag" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      style={compact ? { padding: "40px" } : undefined}
    >
      {!compact && <div className="qw-dropzone__title">Drop images here</div>}
      {!compact && <div className="qw-dropzone__or">or</div>}
      <button className="qw-btn" onClick={pick}>
        {compact ? "Add more images" : "Select Images"}
      </button>
      {!compact && <div className="qw-dropzone__formats">JPG · JPEG · PNG · WEBP</div>}
      <input
        ref={inputRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
        multiple
        hidden
        onChange={(e) => {
          const files = Array.from(e.target.files || []);
          if (files.length) onFiles(files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
