import React, { useState, useEffect } from "react";
import { DataProvider, useData } from "./context/DataContext";
import { SalesProvider } from "./context/SalesContext";
import { Sidebar } from "./components/layout/Sidebar";
import { Header } from "./components/layout/Header";
import { PerformanceView } from "./components/performance/PerformanceView";
import { DropCalendarView } from "./components/performance/DropCalendarView";
import { DataExplorerView } from "./components/data-explorer/DataExplorerView";
import { LivePulseView } from "./components/live-pulse/LivePulseView";
import { SalesPortalView } from "./components/sales/SalesPortalView";
import { AdminLoginView } from "./components/auth/AdminLoginView";
import { getCurrentSession, logoutAdmin, type SessionUser } from "./services/api";
import { SessionProvider } from "./context/SessionContext";
type PortalMode = "admin" | "sales";

const STORAGE_KEY_PORTAL = "cmcb_portal_mode";

const AdminDashboardContent: React.FC<{ onSwitchToSales: () => void; onLogout: () => void }> = ({
  onSwitchToSales,
  onLogout,
}) => {
  const { activeTab } = useData();
  return (
    <div className="flex h-screen w-screen overflow-hidden flex-col lg:flex-row bg-slate-50 font-sans text-slate-900 antialiased">
      {/* Left Sidebar Navigation */}
      <Sidebar onSwitchToSales={onSwitchToSales} onLogout={onLogout} />

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col min-w-0 min-h-0 overflow-hidden">
        {activeTab !== "live-pulse" && <div className={activeTab === "performance" ? "lg:hidden" : ""}><Header onSwitchToSales={onSwitchToSales} onLogout={onLogout} /></div>}
        <main className="flex-1 min-h-0 min-w-0 overflow-hidden flex flex-col">
          {activeTab === "live-pulse" && <LivePulseView />}
          {activeTab === "performance" && <PerformanceView />}
          {activeTab === "drop-calendar" && <DropCalendarView />}
          {activeTab === "data-explorer" && <DataExplorerView />}
        </main>
      </div>
    </div>
  );
};

export function App() {
  const [portalMode, setPortalMode] = useState<PortalMode>(() => {
    const requested = new URLSearchParams(window.location.search).get("portal")?.toLowerCase();
    return requested === "sales" || requested === "sale" || localStorage.getItem(STORAGE_KEY_PORTAL) === "sales" ? "sales" : "admin";
  });
  const [session, setSession] = useState<SessionUser | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  useEffect(() => {
    let alive = true;
    const expired = () => { setSession(null); setIsCheckingAuth(false); };
    window.addEventListener("cmcb-session-expired", expired);
    getCurrentSession().then((user) => {
      if (alive) { setSession(user); setIsCheckingAuth(false); }
    });
    return () => { alive = false; window.removeEventListener("cmcb-session-expired", expired); };
  }, []);
  const handleLogout = async () => { await logoutAdmin(); setSession(null); };
  const handleSetPortalMode = (mode: PortalMode) => {
    setPortalMode(mode);
    const url = new URL(window.location.href);
    if (mode === "sales") {
      localStorage.setItem(STORAGE_KEY_PORTAL, "sales"); url.searchParams.set("portal", "sales");
    } else {
      localStorage.removeItem(STORAGE_KEY_PORTAL); url.searchParams.delete("portal");
    }
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
  };
  if (isCheckingAuth) return <div className="flex min-h-screen items-center justify-center bg-slate-900 text-slate-400"><div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" /></div>;
  if (!session) return <AdminLoginView onLoginSuccess={setSession} onGoToSales={() => handleSetPortalMode("sales")} />;
  return <SessionProvider session={session}>
    {portalMode === "sales"
      ? <SalesProvider key={session.username}><SalesPortalView onSwitchToAdmin={() => handleSetPortalMode("admin")} /></SalesProvider>
      : <DataProvider key={session.username}><AdminDashboardContent onSwitchToSales={() => handleSetPortalMode("sales")} onLogout={handleLogout} /></DataProvider>}
  </SessionProvider>;
}

export default App;
