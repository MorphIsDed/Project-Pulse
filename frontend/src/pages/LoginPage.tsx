import { useState, type FormEvent } from "react";

import { useAuth } from "../auth/AuthContext";
import { ApiError } from "../lib/api";

type HealthState = "loading" | "online" | "offline";

type LoginPageProps = {
  health: HealthState;
  status: string;
};

export default function LoginPage({ health, status }: LoginPageProps) {
  const { login } = useAuth();
  const [email, setEmail] = useState("owner@demo.local");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login(email, password, remember);
    } catch (reason) {
      setError(
        reason instanceof ApiError
          ? reason.message
          : "Unable to sign in right now.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  const dotClass =
    health === "online" ? "dot online" : health === "offline" ? "dot offline" : "dot";

  return (
    <section className="auth">
      <p className="eyebrow">Sign in</p>
      <h1>Welcome back.</h1>
      <p className="intro">
        Use a seeded demo account to explore the planning workspace.
      </p>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="username"
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={remember}
            onChange={(event) => setRemember(event.target.checked)}
          />
          Keep me signed in
        </label>

        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}

        <button type="submit" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="hint">
        Demo accounts: owner@demo.local, editor@demo.local, viewer@demo.local
        <br />
        Password: DemoPulse123!
      </p>

      <div className="status">
        <span className={dotClass} />
        {status}
      </div>
    </section>
  );
}
