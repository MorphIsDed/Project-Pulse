import { type FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  acceptInvitation,
  createInvitation,
  listInvitations,
  revokeInvitation,
  type Invitation,
  type Role,
} from "../lib/api";

const INVITE_ROLES: Array<Exclude<Role, "owner">> = [
  "admin",
  "editor",
  "viewer",
];

function message(reason: unknown): string {
  if (reason instanceof ApiError) return reason.message;
  if (reason instanceof Error) return reason.message;
  return "The invitation request could not be completed.";
}

export default function InvitationPanel({
  organizationId,
  canManage,
  onAccepted,
}: {
  organizationId: number;
  canManage: boolean;
  onAccepted?: (organizationId: number) => void;
}) {
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [acceptToken, setAcceptToken] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!canManage) {
      setInvitations([]);
      return;
    }
    let active = true;
    listInvitations(organizationId)
      .then((items) => {
        if (active) setInvitations(items);
      })
      .catch((reason) => {
        if (active) setError(message(reason));
      });
    return () => {
      active = false;
    };
  }, [organizationId, canManage]);

  async function handleInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError(null);
    setNotice(null);
    setAcceptToken(null);
    try {
      const result = await createInvitation(
        organizationId,
        String(data.get("email") ?? "").trim(),
        String(data.get("role") ?? "viewer") as Exclude<Role, "owner">,
      );
      setInvitations((current) => [result.invitation, ...current]);
      setAcceptToken(result.accept_token ?? null);
      setNotice(
        result.accept_token
          ? "Invitation created. Share the token below with the invitee."
          : "Invitation sent by email.",
      );
      form.reset();
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(invitation: Invitation) {
    setBusy(true);
    setError(null);
    try {
      await revokeInvitation(organizationId, invitation.id);
      setInvitations((current) =>
        current.filter((item) => item.id !== invitation.id),
      );
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function handleAccept(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await acceptInvitation(
        String(data.get("token") ?? "").trim(),
      );
      setNotice("Invitation accepted.");
      form.reset();
      onAccepted?.(result.organization_id);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="invitation-panel">
      <h3>Invitations</h3>
      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? <p className="form-notice">{notice}</p> : null}

      {canManage ? (
        <>
          {invitations.length > 0 ? (
            <ul className="item-list compact">
              {invitations.map((invitation) => (
                <li className="member-row" key={invitation.id}>
                  <span>
                    <strong>{invitation.email}</strong>
                    <span className="role-chip small">
                      {invitation.role}
                    </span>
                  </span>
                  <button
                    type="button"
                    className="danger"
                    onClick={() => void handleRevoke(invitation)}
                    disabled={busy}
                  >
                    Revoke
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">No pending invitations.</p>
          )}

          {acceptToken ? (
            <p className="invitation-token">
              Invite token: <code>{acceptToken}</code>
            </p>
          ) : null}

          <form className="stack-form" onSubmit={handleInvite}>
            <div className="form-row">
              <label className="field">
                Invite email
                <input
                  name="email"
                  type="email"
                  placeholder="person@example.com"
                  required
                />
              </label>
              <label className="field">
                Invitation role
                <select name="role" defaultValue="viewer">
                  {INVITE_ROLES.map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button type="submit" disabled={busy}>
              Send invitation
            </button>
          </form>
        </>
      ) : null}

      <form className="stack-form" onSubmit={handleAccept}>
        <label className="field">
          Have an invitation token?
          <input name="token" placeholder="Paste invitation token" required />
        </label>
        <button type="submit" disabled={busy}>
          Accept invitation
        </button>
      </form>
    </section>
  );
}
