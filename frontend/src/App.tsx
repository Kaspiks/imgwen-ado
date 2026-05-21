import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { WorkspaceLayout } from "./components/WorkspaceLayout";
import { useAuth } from "./context/AuthContext";
import { HistoryPage } from "./pages/HistoryPage";
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { RegisterPage } from "./pages/RegisterPage";
import { StyleExplorationPage } from "./pages/StyleExplorationPage";
import { WorkspacePage } from "./pages/WorkspacePage";

function RequireAuth() {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="flex h-screen items-center justify-center text-sm text-zinc-400">
        Loading...
      </div>
    );
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

function RedirectIfAuthed() {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="flex h-screen items-center justify-center text-sm text-zinc-400">
        Loading...
      </div>
    );
  if (user) return <Navigate to="/" replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route element={<RedirectIfAuthed />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/" element={<LandingPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/workspace" element={<WorkspaceLayout />}>
            <Route index element={<WorkspacePage />} />
            <Route path="history" element={<HistoryPage />} />
          </Route>
          <Route path="/style-exploration" element={<StyleExplorationPage />} />
          <Route
            path="/history"
            element={<Navigate to="/workspace/history" replace />}
          />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
