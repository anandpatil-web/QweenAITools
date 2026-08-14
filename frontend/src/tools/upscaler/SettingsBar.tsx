import type { AppConfig } from "../../lib/types";

interface Props {
  config: AppConfig;
  scale: number;
  creativity: number;
  suffix: string;
  concurrency: number;
  sampleName: string;
  disabled?: boolean;
  onScale: (v: number) => void;
  onCreativity: (v: number) => void;
  onSuffix: (v: string) => void;
  onConcurrency: (v: number) => void;
}

function previewName(sample: string, suffix: string): string {
  const dot = sample.lastIndexOf(".");
  if (dot <= 0) return `${sample}${suffix}`;
  return `${sample.slice(0, dot)}${suffix}${sample.slice(dot)}`;
}

function clampRound(v: number, min: number, max: number): number {
  if (Number.isNaN(v)) return min;
  return Math.max(min, Math.min(max, v));
}

export function SettingsBar({
  config,
  scale,
  creativity,
  suffix,
  concurrency,
  sampleName,
  disabled,
  onScale,
  onCreativity,
  onSuffix,
  onConcurrency,
}: Props) {
  return (
    <div className="qw-settings">
      <div className="qw-field">
        <span className="qw-field__label">Scale factor · {scale}×</span>
        <div className="qw-slider">
          <input
            className="qw-range"
            type="range"
            min={config.scale_min}
            max={config.scale_max}
            step={1}
            value={scale}
            disabled={disabled}
            onChange={(e) => onScale(Number(e.target.value))}
          />
          <input
            className="qw-input qw-input--num"
            type="number"
            min={config.scale_min}
            max={config.scale_max}
            step={0.5}
            value={scale}
            disabled={disabled}
            onChange={(e) =>
              onScale(clampRound(parseFloat(e.target.value), config.scale_min, config.scale_max))
            }
          />
        </div>
      </div>

      <div className="qw-field">
        <span className="qw-field__label">Creativity · {creativity}</span>
        <div className="qw-slider">
          <input
            className="qw-range"
            type="range"
            min={config.creativity_min}
            max={config.creativity_max}
            step={0.5}
            value={creativity}
            disabled={disabled}
            onChange={(e) => onCreativity(Number(e.target.value))}
          />
          <input
            className="qw-input qw-input--num"
            type="number"
            min={config.creativity_min}
            max={config.creativity_max}
            step={0.5}
            value={creativity}
            disabled={disabled}
            onChange={(e) =>
              onCreativity(
                clampRound(parseFloat(e.target.value), config.creativity_min, config.creativity_max),
              )
            }
          />
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
