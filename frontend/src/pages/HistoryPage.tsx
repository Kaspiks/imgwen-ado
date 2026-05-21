import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { EvolutionTimeline } from "../components/EvolutionTimeline";
import { API_BASE, apiFetch } from "../lib/api";

export function HistoryPage() {
  const [params] = useSearchParams();
  const projectIdParam = params.get("projectId");
  const projectId = Number(projectIdParam);
  const [projectName, setProjectName] = useState<string | null>(null);

  useEffect(() => {
    setProjectName(null);
    if (!projectIdParam) return;
    let cancelled = false;
    apiFetch(`${API_BASE}/projects/${projectIdParam}`)
      .then((r) => (r.ok ? (r.json() as Promise<{ project_name: string }>) : null))
      .then((p) => {
        if (!cancelled && p) setProjectName(p.project_name);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [projectIdParam]);

  if (!projectIdParam || Number.isNaN(projectId)) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-10 sm:px-6">
        <h1 className="text-3xl font-bold text-zinc-900">Project evolution</h1>
        <p className="mt-2 text-sm text-zinc-600">
          No project selected. Open a project from{" "}
          <Link to="/projects" className="font-semibold text-accent hover:underline">
            All projects
          </Link>{" "}
          to see its edit history.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[900px] px-4 py-10 sm:px-6">
      <div className="mb-8">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-bold text-zinc-900">
            {projectName ?? `Project #${projectId}`}
          </h1>
          <Link
            to={`/workspace?projectId=${projectId}`}
            className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-semibold text-zinc-700 hover:bg-zinc-50"
          >
            Open in Assistant
          </Link>
        </div>
        <p className="mt-2 text-sm text-zinc-600">
          Every edit session for this project, newest first — base image, the prompt that was run, and
          the edited outputs.
        </p>
      </div>
      <EvolutionTimeline projectId={projectId} />
    </div>
  );
}
