import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NotificationPanel from "./NotificationPanel";
import type { Notification } from "../lib/api";

const apiMocks = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, ...apiMocks };
});

const notification: Notification = {
  id: 4,
  organization_id: 1,
  project_id: 2,
  task_id: 3,
  kind: "task_created",
  message: "Editor added task 'Build' to Launch.",
  read_at: null,
  created_at: "2026-01-05T00:00:00Z",
};

beforeEach(() => {
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
  apiMocks.listNotifications.mockResolvedValue([notification]);
  apiMocks.markNotificationRead.mockResolvedValue({
    ...notification,
    read_at: "2026-01-05T01:00:00Z",
  });
  apiMocks.markAllNotificationsRead.mockResolvedValue(1);
});

describe("NotificationPanel", () => {
  it("marks one notification as read", async () => {
    const browser = userEvent.setup();
    render(<NotificationPanel />);

    expect(await screen.findByText("1 unread")).toBeInTheDocument();
    await browser.click(screen.getByRole("button", { name: "Mark read" }));

    await waitFor(() =>
      expect(apiMocks.markNotificationRead).toHaveBeenCalledWith(4),
    );
    expect(await screen.findByText("read")).toBeInTheDocument();
    expect(screen.getByText("You are all caught up.")).toBeInTheDocument();
  });

  it("marks all notifications as read", async () => {
    const browser = userEvent.setup();
    render(<NotificationPanel />);

    await screen.findByText("1 unread");
    await browser.click(screen.getByRole("button", { name: "Mark all read" }));

    await waitFor(() =>
      expect(apiMocks.markAllNotificationsRead).toHaveBeenCalled(),
    );
    expect(screen.getByText("You are all caught up.")).toBeInTheDocument();
  });
});
