import { Card } from "../components/Card";

export function SettingsPage() {
  return (
    <div className="mx-auto max-w-[640px] px-4 py-10 sm:px-6">
      <h1 className="text-3xl font-bold text-zinc-900">Settings</h1>
      <p className="mt-2 text-sm text-zinc-600">Placeholder preferences for the Stylist AI shell.</p>
      <Card className="mt-8 space-y-6">
        <label className="block">
          <span className="text-sm font-semibold text-zinc-800">Display name</span>
          <input
            type="text"
            defaultValue="Creative lead"
            className="mt-2 w-full rounded-xl border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/40"
          />
        </label>
        <label className="block">
          <span className="text-sm font-semibold text-zinc-800">Default project</span>
          <select className="mt-2 w-full rounded-xl border border-zinc-200 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent/40">
            <option>Spring lookbook</option>
            <option>E‑commerce hero set</option>
          </select>
        </label>
        <label className="flex items-center gap-3">
          <input type="checkbox" defaultChecked className="h-4 w-4 rounded border-zinc-300 text-accent" />
          <span className="text-sm text-zinc-700">Show stylist suggestions in workspace</span>
        </label>
      </Card>
    </div>
  );
}
