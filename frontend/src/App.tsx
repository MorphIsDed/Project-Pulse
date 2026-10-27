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

  if (loading) return <main className="session-loading" role="status">Loading your workspace…</main>;
  if (user) return <WorkspacePage userName={user.display_name} onLogout={logout} />;
  return <main className="login-shell"><div className="brand"><span className="mark">P</span> ProjectPulse</div><LoginPage health={health} status={healthText} /><footer>Your plans. A clearer perspective.</footer></main>;
}

export default function App() {
  return <AuthProvider><AppContent /></AuthProvider>;
}
