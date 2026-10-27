import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InvitationPanel from "./InvitationPanel";
import type { Invitation } from "../lib/api";

const apiMocks = vi.hoisted(() => ({
  listInvitations: vi.fn(),
  createInvitation: vi.fn(),
  revokeInvitation: vi.fn(),
  acceptInvitation: vi.fn(),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, ...apiMocks };
});

const invitation: Invitation = {
  id: 8,
  organization_id: 1,
  email: "invitee@example.com",
  role: "editor",
  expires_at: "2026-02-01T00:00:00Z",
  accepted_at: null,
  created_at: "2026-01-25T00:00:00Z",
};

beforeEach(() => {
  Object.values(apiMocks).forEach((mock) => mock.mockReset());
  apiMocks.listInvitations.mockResolvedValue([invitation]);
  apiMocks.createInvitation.mockResolvedValue({
    invitation: { ...invitation, id: 9, email: "new@example.com" },
    accept_token: "invite-token-123",
  });
  apiMocks.acceptInvitation.mockResolvedValue({ organization_id: 1 });
});

describe("InvitationPanel", () => {
  it("creates an invitation and shows the dev token", async () => {
    const browser = userEvent.setup();
    render(
      <InvitationPanel organizationId={1} canManage />,
    );

    expect(await screen.findByText("invitee@example.com")).toBeInTheDocument();
    await browser.type(
      screen.getByLabelText("Invite email"),
      "new@example.com",
    );
    await browser.selectOptions(
      screen.getByLabelText("Invitation role"),
      "admin",
    );
    await browser.click(
      screen.getByRole("button", { name: "Send invitation" }),
    );

    await waitFor(() =>
      expect(apiMocks.createInvitation).toHaveBeenCalledWith(
        1,
        "new@example.com",
        "admin",
      ),
    );
    expect(await screen.findByText("invite-token-123")).toBeInTheDocument();
  });

  it("accepts an invitation and revokes a pending one", async () => {
    const browser = userEvent.setup();
    const onAccepted = vi.fn();
    render(
      <InvitationPanel
        organizationId={1}
        canManage
        onAccepted={onAccepted}
      />,
    );

    await screen.findByText("invitee@example.com");
    await browser.click(screen.getByRole("button", { name: "Revoke" }));
    await waitFor(() =>
      expect(apiMocks.revokeInvitation).toHaveBeenCalledWith(1, 8),
    );

    await browser.type(
      screen.getByLabelText("Have an invitation token?"),
      "token-abc",
    );
    await browser.click(
      screen.getByRole("button", { name: "Accept invitation" }),
    );
    await waitFor(() =>
      expect(apiMocks.acceptInvitation).toHaveBeenCalledWith("token-abc"),
    );
    expect(onAccepted).toHaveBeenCalledWith(1);
  });
});
