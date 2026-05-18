import { EvolutionTimeline } from "../components/EvolutionTimeline";
import { MOCKUPS } from "../mockups";

export function HistoryPage() {
  return (
    <div className="mx-auto max-w-[900px] px-4 py-10 sm:px-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-zinc-900">Project evolution</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Vertical timeline of milestones—each card is a decision point you can reference in exports.
        </p>
      </div>
      <div className="mb-8 overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-50">
        <img src={MOCKUPS.history} alt="Reference layout" className="w-full object-cover opacity-90" />
      </div>
      <EvolutionTimeline />
    </div>
  );
}
