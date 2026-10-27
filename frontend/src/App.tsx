import { useEffect, useState } from "react";

import { AuthProvider, useAuth } from "./auth/AuthContext";
import LoginPage from "./pages/LoginPage";
import WorkspacePage from "./pages/WorkspacePage";

type Health = { status: string; service: string };
type HealthState = "loading" | "online" | "offline";

function AppContent() {
  const { user, loading, logout } = useAuth();
  const [health, setHealth] = useState<HealthState>("loading");
  const [healthText, setHealthText] = useState("Connecting to API…");
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    let active = true;

    fetch("/api/v1/health")
      .then((response) => {
        if (!response.ok) throw new Error("API is not responding");
        return response.json() as Promise<Health>;
      })
      .then(() => {
        if (!active) return;
        setHealth("online");
        setHealthText("API connected");
      })
      .catch(() => {
        if (!active) return;
        setHealth("offline");
        setHealthText("API unavailable — start the backend");
      });

    return () => {
      active = false;
    };
  }, []);

  async function handleLogout() {
    setSigningOut(true);
    try {
      await logout();
    } catch {
      setSigningOut(false);
      return;
    }
    setSigningOut(false);
  }

  return (
    <main className="shell">
      <header className="topbar">
        <span className="mark">P</span>
        <span>ProjectPulse</span>
        <span className="tag">LOCAL PLANNING</span>
        {user ? (
          <>
            <span className="user-chip">{user.display_name}</span>
            <button
              className="link-button"
              type="button"
              onClick={handleLogout}
              disabled={signingOut}
            >
              {signingOut ? "Signing out…" : "Sign out"}
            </button>
          </>
        ) : null}
      </header>

      {loading ? (
        <section className="welcome">
          <p className="eyebrow">LOADING SESSION</p>
          <h1>One moment.</h1>
        </section>
      ) : user ? (
        <WorkspacePage />
      ) : (
        <LoginPage health={health} status={healthText} />
      )}

      <footer>
        ProjectPulse <span>•</span> Academic planning workspace
      </footer>
    </main>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
