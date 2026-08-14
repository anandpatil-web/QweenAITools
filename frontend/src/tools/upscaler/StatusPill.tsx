import type { ImageStatus } from "../../lib/types";
import { statusLabel } from "../../lib/format";

const ACTIVE: ImageStatus[] = ["uploading", "processing", "downloading"];

export function StatusPill({ status }: { status: ImageStatus }) {
  const isActive = ACTIVE.includes(status);
  const cls =
    status === "done"
      ? "is-done"
      : status === "failed"
        ? "is-failed"
        : status === "timeout"
          ? "is-timeout"
          : isActive
            ? "is-active"
            : "";

  return (
    <span className={`qw-status ${cls}`}>
      {isActive ? (
        <span className="qw-spin" aria-hidden />
      ) : (
        <span className="qw-status__dot" aria-hidden />
      )}
      {status === "done" ? "✓ " : ""}
      {status === "failed" || status === "timeout" ? "× " : ""}
      {statusLabel(status)}
    </span>
  );
}
