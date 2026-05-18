import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { WorkspaceLayout } from "./components/WorkspaceLayout";
import { HistoryPage } from "./pages/HistoryPage";
import { LandingPage } from "./pages/LandingPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StyleExplorationPage } from "./pages/StyleExplorationPage";
import { WorkspacePage } from "./pages/WorkspacePage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/workspace" element={<WorkspaceLayout />}>
          <Route index element={<WorkspacePage />} />
          <Route path="history" element={<HistoryPage />} />
        </Route>
        <Route path="/style-exploration" element={<StyleExplorationPage />} />
        <Route path="/history" element={<Navigate to="/workspace/history" replace />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
