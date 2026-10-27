import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RiskSimulationPanel from "./RiskSimulationPanel";
import type { RiskSimulation } from "../lib/api";

const apiMocks = vi.hoisted(() => ({
  runRiskSimulation: vi.fn(),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, ...apiMocks };
});

const simulation: RiskSimulation = {
  project_id: 100,
  project_version: 4,
  iterations: 500,
  seed: 42,
  target_finish: "2026-01-16",
  deterministic_finish: "2026-01-13",
  finish_percentiles: {
    p10: "2026-01-09",
    p50: "2026-01-13",
    p80: "2026-01-15",
    p90: "2026-01-19",
    p95: "2026-01-21",
  },
  target_probability: 0.8,
  tasks: [
    {
      task_id: 1,
      task_name: "Discovery",
      duration_work_minutes: 960,
      estimates: {
        optimistic: 480,
        most_likely: 960,
        pessimistic: 1920,
      },
      p10_work_minutes: 720,
      p50_work_minutes: 960,
      p90_work_minutes: 1440,
      critical_frequency: 1,
    },
  ],
  warnings: [],
  assumptions: ["Task durations use PERT beta distributions."],
};

beforeEach(() => {
  apiMocks.runRiskSimulation.mockReset();
  apiMocks.runRiskSimulation.mockResolvedValue(simulation);
});

describe("RiskSimulationPanel", () => {
  it("runs a simulation and renders percentiles", async () => {
    const browser = userEvent.setup();
    render(<RiskSimulationPanel projectId={100} canRun />);

    const iterations = screen.getByLabelText("Iterations");
    await browser.clear(iterations);
    await browser.type(iterations, "500");
    await browser.type(screen.getByLabelText("Seed (optional)"), "42");
    await browser.click(screen.getByRole("button", { name: "Run simulation" }));

    await waitFor(() =>
      expect(apiMocks.runRiskSimulation).toHaveBeenCalledWith(100, {
        iterations: 500,
        seed: 42,
      }),
    );
    expect(await screen.findByText("2026-01-19")).toBeInTheDocument();
    expect(screen.getByText(/80.0% chance of meeting 2026-01-16/)).toBeInTheDocument();
    expect(screen.getByText("Discovery")).toBeInTheDocument();
    expect(screen.getByText("100.0%")).toBeInTheDocument();
  });

  it("hides the form for read-only members", () => {
    render(<RiskSimulationPanel projectId={100} canRun={false} />);
    expect(
      screen.queryByRole("button", { name: "Run simulation" }),
    ).not.toBeInTheDocument();
  });
});
