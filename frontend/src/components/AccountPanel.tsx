import { type FormEvent, useState } from "react";

import { ApiError, accountExportUrl, deleteAccount } from "../lib/api";

function message(reason: unknown): string {
  if (reason instanceof ApiError) return reason.message;
  if (reason instanceof Error) return reason.message;
  return "The account request could not be completed.";
}

export default function AccountPanel({
  onDeleted,
}: {
  onDeleted?: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleDelete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError(null);
    try {
      await deleteAccount(String(data.get("password") ?? ""));
      form.reset();
      onDeleted?.();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel">
      <h2>Account</h2>
      <p className="muted">
        Export a JSON copy of your account and the organizations you belong to.
      </p>
      <a className="button-link" href={accountExportUrl()}>
        Export account data
      </a>

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}

      <form className="stack-form danger-zone" onSubmit={handleDelete}>
        <label className="field">
          Delete account password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
          />
        </label>
        <p className="muted">
          Deleting your account removes sole-member organizations. Shared
          organization data remains for the other members.
        </p>
        <button type="submit" className="danger" disabled={busy}>
          Delete my account
        </button>
      </form>
    </section>
  );
}
