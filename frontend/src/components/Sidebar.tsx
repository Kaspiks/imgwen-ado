import { useEffect, useState } from "react";
import { NavLink, useSearchParams } from "react-router-dom";
import { API_BASE } from "../lib/api";

const subLink = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-3 py-2 text-sm ${
    isActive ? "bg-accent/10 font-medium text-accent" : "text-zinc-600 hover:bg-zinc-100"
  }`;

export function Sidebar() {
  const [params] = useSearchParams();
  const projectId = params.get("projectId");
  const [projectName, setProjectName] = useState<string | null>(null);

  useEffect(() => {
    setProjectName(null);
    if (!projectId) return;

    let cancelled = false;
    fetch(`${API_BASE}/projects/${projectId}`)
      .then((r) => (r.ok ? (r.json() as Promise<{ project_name: string }>) : null))
      .then((p) => {
        if (!cancelled && p) setProjectName(p.project_name);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const suffix = projectId ? `?projectId=${projectId}` : "";

  return (
    <aside className="flex w-56 shrink-0 flex-col gap-6 border-r border-zinc-200/80 bg-white p-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Current project</p>
        <p className="mt-1 font-semibold text-zinc-900">
          {projectName ?? (projectId ? `Project #${projectId}` : "No project selected")}
        </p>
      </div>
      <nav className="flex flex-col gap-1">
        <NavLink to={`/workspace${suffix}`} className={subLink} end>
          Assistant
        </NavLink>
        <NavLink to={`/workspace/history${suffix}`} className={subLink}>
          Evolution
        </NavLink>
        <NavLink to="/projects" className={subLink}>
          All projects
        </NavLink>
      </nav>
    </aside>
  );
}
