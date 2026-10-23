import { useEffect, useState } from "react";

type Health = { status: string; service: string };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/v1/health")
      .then((response) => {
        if (!response.ok) throw new Error("API is not responding");
        return response.json() as Promise<Health>;
      })
      .then(setHealth)
      .catch((reason: Error) => setError(reason.message));
  }, []);

  return (
    <main className="shell">
      <header className="topbar"><span className="mark">P</span><span>ProjectPulse</span><span className="tag">LOCAL PLANNING</span></header>
      <section className="welcome">
        <p className="eyebrow">PROJECT MANAGEMENT, MADE CLEAR</p>
        <h1>Make the plan.<br /><em>See what moves.</em></h1>
        <p className="intro">Your workspace for building project plans, understanding dependencies, and making confident decisions.</p>
        <div className="status"><span className={health ? "dot online" : error ? "dot offline" : "dot"} />{health ? "API connected" : error ? "API unavailable — start the backend" : "Connecting to API…"}</div>
      </section>
      <footer>ProjectPulse <span>•</span> Academic planning workspace</footer>
    </main>
  );
}
