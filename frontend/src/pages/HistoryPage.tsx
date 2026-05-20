import { useSearchParams } from "react-router-dom";
import { EvolutionTimeline } from "../components/EvolutionTimeline";

export function HistoryPage() {
  const [params] = useSearchParams();
  const projectId = Number(params.get("projectId")) || 1;

  return (
    <div className="mx-auto max-w-[900px] px-4 py-10 sm:px-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-900">Project evolution</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Vertical timeline of milestones—each card is a decision point you can reference in exports.
        </p>
      </div>
      <EvolutionTimeline projectId={projectId} />
    </div>
  );
}
