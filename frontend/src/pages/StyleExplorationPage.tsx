import { Link, useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { Card } from "../components/Card";
import {
  fetchReferenceLibrary,
  libraryItemToTile,
  type StyleTile,
} from "../lib/references";

function buildFilters(tiles: StyleTile[]): string[] {
  const tags = new Set<string>();
  for (const tile of tiles) {
    if (tile.tag.trim()) tags.add(tile.tag);
  }
  return ["All", ...Array.from(tags).sort((a, b) => a.localeCompare(b))];
}

export function StyleExplorationPage() {
  const navigate = useNavigate();
  const [active, setActive] = useState("All");
  const [selectedTile, setSelectedTile] = useState<StyleTile | null>(null);
  const [tiles, setTiles] = useState<StyleTile[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);

    fetchReferenceLibrary()
      .then((items) => {
        if (cancelled) return;
        setTiles(items.map(libraryItemToTile));
      })
      .catch((err) => {
        if (cancelled) return;
        setTiles([]);
        setLoadError(err instanceof Error ? err.message : "Failed to load references");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const filters = useMemo(() => buildFilters(tiles), [tiles]);
  const filtered = tiles.filter((t) => active === "All" || t.tag === active);
  const drawerOpen = selectedTile !== null;

  const handleDownload = (tile: StyleTile) => {
    const a = document.createElement("a");
    a.href = tile.src;
    a.download = tile.title.replaceAll(" ", "_") + ".png";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="relative mx-auto max-w-[1200px] px-4 py-10 sm:px-6">
      <div className="mb-6 rounded-xl border border-accent/20 bg-accent/5 px-4 py-3 text-sm text-zinc-800">
        References saved or uploaded in{" "}
        <Link to="/workspace" className="font-semibold underline decoration-accent/40 hover:text-accent">
          Workspace → Assistant
        </Link>{" "}
        appear here automatically. Pick one to preload it into a new edit session.
      </div>

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-zinc-900">Style exploration</h1>
          <p className="text-sm text-zinc-600">
            Browse your reference library and inspect style breakdowns.
          </p>
        </div>
      </div>

      {loadError ? (
        <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          Could not load the reference library: {loadError}
        </div>
      ) : null}

      {filters.length > 1 ? (
        <div className="mb-6 flex flex-wrap gap-2">
          {filters.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setActive(f)}
              className={`rounded-full px-4 py-1.5 text-xs font-semibold transition ${
                active === f
                  ? "bg-accent text-white shadow-sm"
                  : "bg-white text-zinc-600 ring-1 ring-zinc-200 hover:bg-zinc-50"
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      ) : null}

      {loading ? (
        <p className="py-16 text-center text-sm text-zinc-400">Loading reference library…</p>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-zinc-300 bg-white/70 px-6 py-16 text-center">
          <p className="text-sm font-semibold text-zinc-800">No references yet</p>
          <p className="mt-2 text-sm text-zinc-500">
            Upload a reference in the workspace or click Save to library — it will show up here.
          </p>
          <Link
            to="/workspace"
            className="mt-4 inline-block rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-white hover:bg-[#4f4ddb]"
          >
            Open workspace
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSelectedTile(t)}
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
      )}

      <div
        className={`fixed inset-0 z-50 bg-black/30 transition-opacity ${drawerOpen ? "opacity-100" : "pointer-events-none opacity-0"}`}
        aria-hidden={!drawerOpen}
        onClick={() => setSelectedTile(null)}
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
          <h2 className="text-lg font-bold text-zinc-900">
            {selectedTile?.title ?? "Style analysis"}
          </h2>
          <button
            type="button"
            onClick={() => setSelectedTile(null)}
            className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100"
            aria-label="Close panel"
          >
            ✕
          </button>
        </div>
        {selectedTile && (
          <div className="flex-1 overflow-y-auto p-5">
            <img
              src={selectedTile.src}
              alt={selectedTile.title}
              className="mb-4 w-full rounded-2xl border border-zinc-200"
            />
            <span className="inline-block rounded-full bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
              {selectedTile.tag}
            </span>
            <p className="mt-3 text-sm leading-relaxed text-zinc-600">
              {selectedTile.description}
            </p>
            <h3 className="mb-3 mt-6 text-xs font-bold uppercase tracking-wider text-zinc-400">
              Visual tokens
            </h3>
            <div className="space-y-3">
              {selectedTile.tokens.map((row) => (
                <div key={`${row.k}-${row.v}`} className="rounded-xl bg-zinc-50 px-4 py-3">
                  <p className="text-xs font-semibold text-accent">{row.k}</p>
                  <p className="mt-1 text-sm text-zinc-800">{row.v}</p>
                </div>
              ))}
            </div>
            <div className="mt-8 flex flex-col gap-2">
              <button
                type="button"
                onClick={() => {
                  const params = new URLSearchParams({ ref: selectedTile.src });
                  navigate(`/workspace?${params.toString()}`);
                }}
                className="w-full rounded-xl bg-accent py-3 text-sm font-semibold text-white hover:bg-[#4f4ddb]"
              >
                Add to workspace
              </button>
              <button
                type="button"
                onClick={() => handleDownload(selectedTile)}
                className="w-full rounded-xl border border-zinc-200 py-3 text-sm font-semibold text-zinc-800 hover:bg-zinc-50"
              >
                Save as preset
              </button>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}
