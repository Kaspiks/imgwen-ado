import { Link } from "react-router-dom";
import { useState } from "react";
import { Card } from "../components/Card";
import { MOCKUPS } from "../mockups";

const filters = ["All", "Editorial", "Product", "Portrait", "Campaign", "Minimal"];

const tiles = [
  { id: "t1", tag: "Editorial", title: "Soft daylight", src: MOCKUPS.styleExploration },
  { id: "t2", tag: "Product", title: "Studio gloss", src: MOCKUPS.workspace },
  { id: "t3", tag: "Portrait", title: "Warm key", src: MOCKUPS.projects },
  { id: "t4", tag: "Minimal", title: "Matte neutrals", src: MOCKUPS.landing },
  { id: "t5", tag: "Campaign", title: "High contrast", src: MOCKUPS.history },
  { id: "t6", tag: "Editorial", title: "Film grain", src: MOCKUPS.styleExploration },
];

export function StyleExplorationPage() {
  const [active, setActive] = useState("All");
  const [drawerOpen, setDrawerOpen] = useState(false);

  const filtered = tiles.filter((t) => active === "All" || t.tag === active);

  return (
    <div className="relative mx-auto max-w-[1200px] px-4 py-10 sm:px-6">
      <div className="mb-6 rounded-xl border border-accent/20 bg-accent/5 px-4 py-3 text-sm text-zinc-800">
        <span className="font-semibold text-accent">Live API</span> lives under{" "}
        <Link to="/workspace" className="font-semibold underline decoration-accent/40 hover:text-accent">
          Workspace → Assistant
        </Link>
        . This page is a static mock for layout exploration.
      </div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-zinc-900">Style exploration</h1>
          <p className="text-sm text-zinc-600">Browse trending directions and inspect token breakdowns.</p>
        </div>
        <button
          type="button"
          onClick={() => setDrawerOpen(true)}
          className="rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-[#4f4ddb]"
        >
          Open style analysis
        </button>
      </div>

      <div className="mb-6 flex flex-wrap gap-2">
        {filters.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setActive(f)}
            className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
              active === f ? "bg-accent text-white shadow-sm" : "bg-white text-zinc-600 ring-1 ring-zinc-200 hover:bg-zinc-50"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="text-left"
          >
            <Card padding="sm" className="overflow-hidden transition hover:shadow-md">
              <div className="aspect-[4/3] overflow-hidden rounded-xl bg-zinc-100">
                <img src={t.src} alt="" className="h-full w-full object-cover" />
              </div>
              <div className="mt-3 flex items-center justify-between">
                <div>
                  <p className="text-sm font-bold text-zinc-900">{t.title}</p>
                  <p className="text-xs text-zinc-500">{t.tag}</p>
                </div>
                <span className="text-xs font-semibold text-accent">Analyze →</span>
              </div>
            </Card>
          </button>
        ))}
      </div>

      <div
        className={`fixed inset-0 z-50 bg-black/30 transition-opacity ${drawerOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}
        aria-hidden={!drawerOpen}
        onClick={() => setDrawerOpen(false)}
      />
      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col border-l border-zinc-200 bg-white shadow-2xl transition-transform duration-300 ${
          drawerOpen ? "translate-x-0" : "translate-x-full"
        }`}
        role="dialog"
        aria-modal="true"
        aria-label="Style analysis"
      >
        <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-4">
          <h2 className="text-lg font-bold text-zinc-900">Style analysis</h2>
          <button
            type="button"
            onClick={() => setDrawerOpen(false)}
            className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100"
            aria-label="Close panel"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <img src={MOCKUPS.styleExploration} alt="" className="mb-4 w-full rounded-2xl border border-zinc-200" />
          <p className="text-sm text-zinc-600">
            Tokenized breakdown of palette, contrast, and texture. Use this to align generations with brand
            guardrails.
          </p>
          <div className="mt-6 space-y-3">
            {[
              { k: "Palette", v: "Sand · Clay · Ink" },
              { k: "Contrast", v: "Medium-high (key separation 0.62)" },
              { k: "Texture", v: "Fine grain, matte skin" },
              { k: "Composition", v: "Rule of thirds, negative space right" },
            ].map((row) => (
              <div key={row.k} className="rounded-xl bg-zinc-50 px-4 py-3">
                <p className="text-xs font-semibold text-accent">{row.k}</p>
                <p className="mt-1 text-sm text-zinc-800">{row.v}</p>
              </div>
            ))}
          </div>
          <div className="mt-8 flex flex-col gap-2">
            <button
              type="button"
              className="w-full rounded-xl bg-accent py-3 text-sm font-semibold text-white hover:bg-[#4f4ddb]"
            >
              Apply to workspace
            </button>
            <button
              type="button"
              className="w-full rounded-xl border border-zinc-200 py-3 text-sm font-semibold text-zinc-800 hover:bg-zinc-50"
            >
              Save as preset
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}
