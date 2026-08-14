import type { AppConfig } from "../../lib/types";

interface Props {
  config: AppConfig;
  scale: number;
  suffix: string;
  concurrency: number;
  sampleName: string;
  disabled?: boolean;
  onScale: (v: number) => void;
  onSuffix: (v: string) => void;
  onConcurrency: (v: number) => void;
}

function previewName(sample: string, suffix: string): string {
  const dot = sample.lastIndexOf(".");
  if (dot <= 0) return `${sample}${suffix}`;
  return `${sample.slice(0, dot)}${suffix}${sample.slice(dot)}`;
}

export function SettingsBar({
  config,
  scale,
  suffix,
  concurrency,
  sampleName,
  disabled,
  onScale,
  onSuffix,
  onConcurrency,
}: Props) {
  return (
    <div className="qw-settings">
      <div className="qw-field">
        <span className="qw-field__label">Scale</span>
        <div className="qw-seg">
          {config.supported_scale_factors.map((s) => (
            <button
              key={s}
              className={s === scale ? "is-on" : ""}
              onClick={() => onScale(s)}
              disabled={disabled}
            >
              {s}×
            </button>
          ))}
        </div>
      </div>

      <div className="qw-field">
        <span className="qw-field__label">Filename suffix</span>
        <input
          className="qw-input"
          value={suffix}
          placeholder="e.g. _x2"
          spellCheck={false}
          disabled={disabled}
          onChange={(e) => onSuffix(e.target.value)}
        />
        <span className="qw-preview-name">
          {sampleName ? previewName(sampleName, suffix) : "ring.jpg → ring.jpg"}
        </span>
      </div>

      <div className="qw-field">
        <span className="qw-field__label">Concurrency</span>
        <div className="qw-seg">
          {config.allowed_concurrency.map((c) => {
            const over = c > config.max_concurrency;
            return (
              <button
                key={c}
                className={c === concurrency ? "is-on" : ""}
                onClick={() => onConcurrency(c)}
                disabled={disabled || over}
                title={over ? `Backend limit is ${config.max_concurrency}` : undefined}
              >
                {c}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
