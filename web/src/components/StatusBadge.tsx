import type { RunStatus } from "../types";

const LABELS: Record<RunStatus, string> = {
  queued: "в очереди",
  running: "выполняется",
  done: "готово",
  failed: "ошибка",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  return <span className={`badge badge-${status}`}>{LABELS[status]}</span>;
}
