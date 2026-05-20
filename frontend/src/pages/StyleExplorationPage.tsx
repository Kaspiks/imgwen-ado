import { Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { Card } from "../components/Card";
import { MOCKUPS } from "../mockups";

const filters = ["All", "Editorial", "Product", "Portrait", "Campaign", "Minimal"];

type Tile = {
  id: string;
  tag: string;
  title: string;
  src: string;
  description: string;
  tokens: { k: string; v: string }[];
};

const tiles: Tile[] = [
  {
    id: "t1",
    tag: "Editorial",
    title: "Soft daylight",
    src: MOCKUPS.styleExploration,
    description: "Warm editorial lighting with shallow depth of field. Ideal for lifestyle and fashion shoots that need an organic, approachable feel.",
    tokens: [
      { k: "Palette", v: "Sand · Clay · Ink" },
      { k: "Contrast", v: "Medium-high (key separation 0.62)" },
      { k: "Texture", v: "Fine grain, matte skin" },
      { k: "Composition", v: "Rule of thirds, negative space right" },
    ],
  },
  {
    id: "t2",
    tag: "Product",
    title: "Studio gloss",
    src: MOCKUPS.workspace,
    description: "Clean studio setup with controlled specular highlights. Works well for product photography and e-commerce hero shots.",
    tokens: [
      { k: "Palette", v: "White · Silver · Charcoal" },
      { k: "Contrast", v: "High (key separation 0.78)" },
      { k: "Texture", v: "Smooth gloss, reflective surfaces" },
      { k: "Lighting", v: "Two-point with softbox fill" },
    ],
  },
  {
    id: "t3",
    tag: "Portrait",
    title: "Warm key",
    src: MOCKUPS.projects,
    description: "Golden-hour inspired portrait lighting with rich skin tones. Suited for headshots and personal branding.",
    tokens: [
      { k: "Palette", v: "Amber · Peach · Espresso" },
      { k: "Contrast", v: "Medium (key separation 0.55)" },
      { k: "Texture", v: "Soft diffusion, skin detail preserved" },
      { k: "Mood", v: "Warm, inviting, personal" },
    ],
  },
  {
    id: "t4",
    tag: "Minimal",
    title: "Matte neutrals",
    src: MOCKUPS.landing,
    description: "Restrained neutral palette with matte finishes. Pairs well with minimalist design systems and editorial layouts.",
    tokens: [
      { k: "Palette", v: "Ivory · Slate · Stone" },
      { k: "Contrast", v: "Low (key separation 0.35)" },
      { k: "Texture", v: "Flat matte, no specular" },
      { k: "Composition", v: "Centered subject, generous whitespace" },
    ],
  },
  {
    id: "t5",
    tag: "Campaign",
    title: "High contrast",
    src: MOCKUPS.history,
    description: "Bold, high-energy look with deep shadows and punchy highlights. Great for campaign visuals and social media hero imagery.",
    tokens: [
      { k: "Palette", v: "Black · Crimson · Electric blue" },
      { k: "Contrast", v: "Very high (key separation 0.91)" },
      { k: "Texture", v: "Sharp edges, dramatic falloff" },
      { k: "Mood", v: "Bold, energetic, attention-grabbing" },
    ],
  },
  {
    id: "t6",
    tag: "Editorial",
    title: "Film grain",
    src: MOCKUPS.styleExploration,
    description: "Analog film emulation with visible grain and slightly lifted blacks. Nostalgic tone for editorial and storytelling work.",
    tokens: [
      { k: "Palette", v: "Olive · Rust · Cream" },
      { k: "Contrast", v: "Medium (key separation 0.52)" },
      { k: "Texture", v: "Visible grain, halation on highlights" },
      { k: "Film stock", v: "Kodak Portra 400 emulation" },
    ],
  },
  {
    id: "t7",
    tag: "Minimal",
    title: "Blue tones palette",
    src: "/1294.png",
    description: "A monochromatic color palette spanning from deep navy to light sky blue. Useful as a color reference for cool-toned edits, backgrounds, and brand palettes.",
    tokens: [
      { k: "Palette", v: "Navy · Teal · Steel blue · Sky · Ice" },
      { k: "Temperature", v: "Cool (strongly cool-shifted)" },
      { k: "Saturation", v: "Medium-high, consistent across swatches" },
      { k: "Usage", v: "Color grading reference, background fills" },
    ],
  },
  {
    id: "t8",
    tag: "Minimal",
    title: "Minimalism, interior",
    src: "/photo_2026-05-18_09-36-43.jpg",
    description: "Satin ribbon roses in pink and blue wrapped in white paper, with a candle gift box. A minimalist interior styling reference with soft textures and a curated pastel color story.",
    tokens: [
      { k: "Palette", v: "Blush pink · Sky blue · Ivory · Charcoal" },
      { k: "Texture", v: "Satin ribbon, matte paper, smooth wax" },
      { k: "Composition", v: "Overhead angle, layered objects, diagonal" },
      { k: "Mood", v: "Delicate, curated, gift-like presentation" },
    ],
  },
];

export function StyleExplorationPage() {
  const navigate = useNavigate();
  const [active, setActive] = useState("All");
  const [selectedTile, setSelectedTile] = useState<Tile | null>(null);

  const filtered = tiles.filter((t) => active === "All" || t.tag === active);
  const drawerOpen = selectedTile !== null;

  const handleDownload = (tile: Tile) => {
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
                <div key={row.k} className="rounded-xl bg-zinc-50 px-4 py-3">
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
