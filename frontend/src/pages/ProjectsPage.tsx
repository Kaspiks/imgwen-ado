import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { CreateProjectModal } from "../components/CreateProjectModal";
import { API_BASE, apiFetch } from "../lib/api";

type ProjectItem = {
  id: number;
  project_name: string;
  status: string;
  creation_date: string;
  total_edits: number;
};

const STATUS_STYLE: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700",
  draft: "bg-zinc-100 text-zinc-600",
  archived: "bg-amber-50 text-amber-700",
};

export function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    apiFetch(`${API_BASE}/projects`)
      .then((r) => (r.ok ? (r.json() as Promise<{ projects: ProjectItem[] }>) : Promise.reject()))
      .then((d) => setProjects(d.projects))
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10 sm:px-6">
      <div className="mb-8 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-zinc-900">Projects</h1>
          <p className="text-sm text-zinc-600">
            Organize stylist sessions and exports in one place.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="self-start rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#4f4ddb]"
        >
          New project
        </button>
      </div>

      {loading && (
        <p className="py-16 text-center text-sm text-zinc-400">Loading projects...</p>
      )}

      {!loading && projects.length === 0 && (
        <Card className="flex flex-col items-center gap-3 py-16">
          <p className="text-sm text-zinc-500">No projects yet.</p>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#4f4ddb]"
          >
            Create your first project
          </button>
        </Card>
      )}

      {!loading && projects.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Link
              key={p.id}
              to={`/workspace?projectId=${p.id}`}
              className="group"
            >
              <Card padding="sm" className="overflow-hidden transition hover:shadow-md">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-zinc-900 group-hover:text-accent">
                      {p.project_name}
                    </p>
                    <p className="mt-1 text-xs text-zinc-400">
                      {new Date(p.creation_date).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                      {p.total_edits > 0 && (
                        <>
                          {" "}· {p.total_edits} edit{p.total_edits !== 1 && "s"}
                        </>
                      )}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
                      STATUS_STYLE[p.status] ?? "bg-zinc-100 text-zinc-600"
                    }`}
                  >
                    {p.status}
                  </span>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <CreateProjectModal open={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
