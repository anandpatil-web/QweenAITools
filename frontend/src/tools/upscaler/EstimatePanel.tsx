import type { ScanResponse } from "../../lib/types";
import { formatInr, formatMegapixels, formatUsd } from "../../lib/format";

interface Props {
  scan: ScanResponse;
  busy: boolean;
  onBack: () => void;
  onConfirm: () => void;
}

export function EstimatePanel({ scan, busy, onBack, onConfirm }: Props) {
  return (
    <div className="qw-estimate qw-section">
      <div className="qw-eyebrow qw-estimate__eyebrow">Ready to upscale</div>

      <div className="qw-estimate__rows">
        <div className="qw-estimate__cell">
          <div className="k">Images</div>
          <div className="v">{scan.total_images}</div>
        </div>
        <div className="qw-estimate__cell">
          <div className="k">Scale</div>
          <div className="v">{scan.scale_factor}×</div>
        </div>
        <div className="qw-estimate__cell">
          <div className="k">Input</div>
          <div className="v">{formatMegapixels(scan.total_input_megapixels)}</div>
        </div>
        <div className="qw-estimate__cell">
          <div className="k">Output</div>
          <div className="v">{formatMegapixels(scan.total_output_megapixels)}</div>
        </div>
      </div>

      <div className="qw-cost">
        <div className="qw-cost__label">Estimated cost</div>
        <div className="qw-cost__usd">{formatUsd(scan.total_cost_usd)}</div>
        <div className="qw-cost__inr">≈ {formatInr(scan.total_cost_inr)}</div>
        <p className="qw-cost__note">
          Based on output megapixels. INR is an approximate estimate; actual
          billing may vary slightly.
        </p>
      </div>

      <div className="qw-estimate__actions">
        <button className="qw-btn qw-btn--ghost" onClick={onBack} disabled={busy}>
          Cancel
        </button>
        <button className="qw-btn qw-btn--gold" onClick={onConfirm} disabled={busy}>
          {busy ? "Starting…" : "Confirm & Run"}
        </button>
      </div>
    </div>
  );
}
