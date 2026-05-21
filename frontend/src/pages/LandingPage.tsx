import { Link } from "react-router-dom";
import { Card } from "../components/Card";
import { WorkflowStrip } from "../components/WorkflowStrip";
export function LandingPage() {
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-10 sm:px-6">
      <section className="grid gap-10 lg:grid-cols-2 lg:items-center">
        <div>
          <p className="text-sm font-semibold text-accent">Stylist AI</p>
          <h1 className="mt-2 text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl">
            Refine visuals with a professional stylist in the loop
          </h1>
          <p className="mt-4 max-w-xl text-lg text-zinc-600">
            Analyze references, get structured suggestions, and iterate with confidence—without losing
            brand consistency.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              to="/workspace"
              className="rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-[#4f4ddb]"
            >
              Open workspace
            </Link>
            <Link
              to="/projects"
              className="rounded-xl border border-zinc-200 bg-white px-5 py-3 text-sm font-semibold text-zinc-800 shadow-sm hover:bg-zinc-50"
            >
              View projects
            </Link>
          </div>
        </div>
        <div className="relative">
          <img
            src="/before-and-after-photoshop-pictures-30.jpg"
            alt="Before and after editing example"
            className="w-full rounded-2xl border border-zinc-200/80 shadow-lg"
          />
          <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-black/5" />
        </div>
      </section>

      <section className="mt-16">
        <Card>
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="max-w-md">
              <h2 className="text-2xl font-bold text-zinc-900">Professional refinement</h2>
              <p className="mt-2 text-sm text-zinc-600">
                Every pass is guided: structured feedback, traceable decisions, and a workflow your team can
                replay.
              </p>
            </div>
            <div className="flex-1 md:max-w-xl">
              <WorkflowStrip />
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
