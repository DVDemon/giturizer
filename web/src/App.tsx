import { useEffect, useState } from "react";

type Health = {
  status: string;
  service: string;
  version: string;
};

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/health")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        return response.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  return (
    <main className="app">
      <header>
        <h1>ArchDiscovery</h1>
        <p className="subtitle">
          Восстановление архитектуры по исходному коду — UI-заглушка (P0)
        </p>
      </header>

      <section className="card">
        <h2>Статус API</h2>
        {health ? (
          <ul className="kv">
            <li>
              status: <strong>{health.status}</strong>
            </li>
            <li>service: {health.service}</li>
            <li>version: {health.version}</li>
          </ul>
        ) : null}
        {error ? <p className="error">Нет связи с API: {error}</p> : null}
        {!health && !error ? <p>Проверяем…</p> : null}
      </section>

      <section className="card">
        <h2>Дальше по плану</h2>
        <p>
          P1 — проекты и запуски. P2 — анализаторы. P5 — Structurizr DSL/JSON. P6 — визуализация
          графа.
        </p>
      </section>
    </main>
  );
}
