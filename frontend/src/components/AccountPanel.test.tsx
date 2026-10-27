import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AccountPanel from "./AccountPanel";

const apiMocks = vi.hoisted(() => ({
  deleteAccount: vi.fn(),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return { ...actual, ...apiMocks };
});

beforeEach(() => {
  apiMocks.deleteAccount.mockReset();
  apiMocks.deleteAccount.mockResolvedValue(undefined);
});

describe("AccountPanel", () => {
  it("links to the account export", () => {
    render(<AccountPanel />);
    expect(
      screen.getByRole("link", { name: "Export account data" }),
    ).toHaveAttribute("href", "/api/v1/account/export");
  });

  it("deletes the account after password confirmation", async () => {
    const browser = userEvent.setup();
    const onDeleted = vi.fn();
    render(<AccountPanel onDeleted={onDeleted} />);

    await browser.type(
      screen.getByLabelText("Delete account password"),
      "CorrectHorse123!",
    );
    await browser.click(
      screen.getByRole("button", { name: "Delete my account" }),
    );

    await waitFor(() =>
      expect(apiMocks.deleteAccount).toHaveBeenCalledWith(
        "CorrectHorse123!",
      ),
    );
    expect(onDeleted).toHaveBeenCalled();
  });
});
