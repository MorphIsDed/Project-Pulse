import { type FormEvent, useState } from "react";

import {
  ApiError,
  runRiskSimulation,
  type RiskSimulation,
} from "../lib/api";

type Props = {
  projectId: number;
  canRun: boolean;
};

function message(reason: unknown): string {
  if (reason instanceof ApiError) return reason.message;
  if (reason instanceof Error) return reason.message;
  return "The risk simulation could not be completed.";
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function RiskSimulationPanel({ projectId, canRun }: Props) {
  const [simulation, setSimulation] = useState<RiskSimulation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const iterations = Number(data.get("iterations")) || 2000;
    const seedValue = String(data.get("seed") ?? "").trim();
    setBusy(true);
    setError(null);
    try {
      setSimulation(
        await runRiskSimulation(projectId, {
          iterations,
          ...(seedValue ? { seed: Number(seedValue) } : {}),
        }),
      );
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="risk-panel">
      <div>
        <h3>Risk simulation</h3>
        <p className="muted">
          Run a seeded Monte Carlo simulation over task duration estimates.
        </p>
      </div>

      {canRun ? (
        <form className="stack-form" onSubmit={handleRun}>
          <div className="form-row">
            <label className="field">
              Iterations
              <input
                name="iterations"
                type="number"
                min="100"
                max="10000"
                step="100"
                defaultValue="2000"
              />
            </label>
            <label className="field">
              Seed (optional)
              <input name="seed" type="number" placeholder="Random" />
            </label>
          </div>
          <button type="submit" disabled={busy}>
            {busy ? "Simulating..." : "Run simulation"}
          </button>
        </form>
      ) : null}

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}

      {simulation ? (
        <div className="risk-results">
          <p className="schedule-meta">
            {simulation.iterations} iterations | seed {simulation.seed} |
            deterministic finish {simulation.deterministic_finish}
            {simulation.target_probability !== null
              ? ` | ${percent(simulation.target_probability)} chance of meeting ${
                  simulation.target_finish
                }`
              : ""}
          </p>

          <div className="schedule-table-wrap">
            <table className="schedule-table">
              <thead>
                <tr>
                  <th>Finish percentile</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(simulation.finish_percentiles).map(
                  ([label, date]) => (
                    <tr key={label}>
                      <td>{label.toUpperCase()}</td>
                      <td>{date}</td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>

          <div className="schedule-table-wrap">
            <table className="schedule-table">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>P10</th>
                  <th>P50</th>
                  <th>P90</th>
                  <th>Critical frequency</th>
                </tr>
              </thead>
              <tbody>
                {simulation.tasks.map((task) => (
                  <tr key={task.task_id}>
                    <td>{task.task_name}</td>
                    <td>{task.p10_work_minutes} min</td>
                    <td>{task.p50_work_minutes} min</td>
                    <td>{task.p90_work_minutes} min</td>
                    <td>{percent(task.critical_frequency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <ul className="item-list compact">
            {simulation.assumptions.map((assumption) => (
              <li key={assumption}>{assumption}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
