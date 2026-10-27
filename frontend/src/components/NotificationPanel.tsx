import { useEffect, useState } from "react";

import {
  ApiError,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type Notification,
} from "../lib/api";

function message(reason: unknown): string {
  if (reason instanceof ApiError) return reason.message;
  if (reason instanceof Error) return reason.message;
  return "Notifications could not be loaded.";
}

export default function NotificationPanel({
  refreshKey = 0,
}: {
  refreshKey?: number;
}) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    listNotifications()
      .then((items) => {
        if (active) setNotifications(items);
      })
      .catch((reason) => {
        if (active) setError(message(reason));
      });
    return () => {
      active = false;
    };
  }, [refreshKey]);

  async function markOne(notification: Notification) {
    setBusy(true);
    setError(null);
    try {
      const updated = await markNotificationRead(notification.id);
      setNotifications((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  async function markAll() {
    setBusy(true);
    setError(null);
    try {
      await markAllNotificationsRead();
      setNotifications((current) =>
        current.map((item) => ({
          ...item,
          read_at: item.read_at ?? new Date().toISOString(),
        })),
      );
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  const unread = notifications.filter((item) => item.read_at === null).length;

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>Notifications</h2>
          <p className="muted">
            {unread === 0 ? "You are all caught up." : `${unread} unread`}
          </p>
        </div>
        {unread > 0 ? (
          <button type="button" onClick={markAll} disabled={busy}>
            Mark all read
          </button>
        ) : null}
      </div>

      {error ? (
        <p className="form-error" role="alert">
          {error}
        </p>
      ) : null}

      {notifications.length === 0 ? (
        <p className="muted">No notifications yet.</p>
      ) : (
        <ul className="item-list compact">
          {notifications.map((notification) => (
            <li className="member-row" key={notification.id}>
              <span>
                <strong>{notification.kind.replaceAll("_", " ")}</strong>
                <br />
                <span className="muted">{notification.message}</span>
              </span>
              {notification.read_at === null ? (
                <button
                  type="button"
                  onClick={() => void markOne(notification)}
                  disabled={busy}
                >
                  Mark read
                </button>
              ) : (
                <span className="role-chip small">read</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
