import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { RevisionTimeline } from "../components/RevisionTimeline";
import { MOCKUPS } from "../mockups";

const projects = [
  { id: "1", name: "Spring lookbook", status: "In review", thumb: MOCKUPS.projects },
  { id: "2", name: "E‑commerce hero set", status: "Draft", thumb: MOCKUPS.workspace },
  { id: "3", name: "Campaign B-roll", status: "Approved", thumb: MOCKUPS.styleExploration },
  { id: "4", name: "Lookbook v2", status: "Archived", thumb: MOCKUPS.history },
];

export function ProjectsPage() {
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10 sm:px-6">
      <div className="mb-8 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-zinc-900">Projects</h1>
          <p className="text-sm text-zinc-600">Organize stylist sessions and exports in one place.</p>
        </div>
        <button
          type="button"
          className="self-start rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#4f4ddb]"
        >
          New project
        </button>
      </div>

      <Card className="mb-10 border-accent/20 bg-gradient-to-br from-white to-accent/5" padding="lg">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-stretch">
          <div className="flex-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-accent">Featured</p>
            <h2 className="mt-2 text-2xl font-bold text-zinc-900">Spring lookbook</h2>
            <p className="mt-2 text-sm text-zinc-600">
              Three refinement rounds with locked palette. Timeline shows revision milestones—open the
              workspace to continue.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                to="/workspace"
                className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#4f4ddb]"
              >
                Open workspace
              </Link>
              <Link
                to="/workspace/history"
                className="rounded-xl border border-zinc-200 bg-white px-4 py-2 text-sm font-semibold text-zinc-800 hover:bg-zinc-50"
              >
                Project evolution
              </Link>
            </div>
          </div>
          <RevisionTimeline />
          <div className="hidden w-48 shrink-0 overflow-hidden rounded-2xl border border-zinc-200 lg:block">
            <img src={MOCKUPS.projects} alt="" className="h-full w-full object-cover" />
          </div>
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((p) => (
          <Card key={p.id} padding="sm" className="overflow-hidden transition hover:shadow-md">
            <div className="aspect-[4/3] overflow-hidden rounded-xl bg-zinc-100">
              <img src={p.thumb} alt="" className="h-full w-full object-cover opacity-90" />
            </div>
            <div className="mt-4 flex items-start justify-between gap-2">
              <div>
                <p className="font-semibold text-zinc-900">{p.name}</p>
                <p className="text-xs text-zinc-500">{p.status}</p>
              </div>
              <Link to="/workspace" className="text-xs font-semibold text-accent hover:underline">
                Open
              </Link>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
