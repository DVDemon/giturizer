import type { Run, RunStatus } from "./types";

const dateFormatter = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "short",
  timeStyle: "short",
});

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return dateFormatter.format(new Date(value));
}

export function formatDuration(run: Run): string {
  if (!run.started_at) {
    return "—";
  }
  const start = new Date(run.started_at).getTime();
  const end = run.finished_at ? new Date(run.finished_at).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  if (seconds < 60) {
    return `${seconds} с`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes} мин ${seconds % 60} с`;
  }
  const hours = Math.floor(minutes / 60);
  return `${hours} ч ${minutes % 60} мин`;
}

const STAGE_LABELS: Record<string, string> = {
  clone: "Клонирование и submodules",
  detect: "Детект технологий",
  analyzers: "Анализаторы",
  deployment: "API и deployment",
  model: "Сборка модели",
  structurizr: "C4 и отчёт",
  report: "C4 и отчёт",
  graph: "Финализация",
  finalize: "Финализация",
  done: "Готово",
  failed: "Ошибка",
};

export function stageLabel(stage: string | null): string {
  if (!stage) {
    return "В очереди";
  }
  return STAGE_LABELS[stage] ?? stage;
}

export function statusLabel(status: RunStatus): string {
  return {
    queued: "в очереди",
    running: "выполняется",
    done: "готово",
    failed: "ошибка",
  }[status];
}

export function pageNumbers(current: number, total: number): Array<number | "…"> {
  if (total <= 7) {
    return Array.from({ length: total }, (_, index) => index + 1);
  }
  const pages = new Set<number>([1, total, current, current - 1, current + 1]);
  const sorted = [...pages].filter((value) => value >= 1 && value <= total).sort((a, b) => a - b);
  const result: Array<number | "…"> = [];
  let previous = 0;
  for (const value of sorted) {
    if (previous && value - previous > 1) {
      result.push("…");
    }
    result.push(value);
    previous = value;
  }
  return result;
}
