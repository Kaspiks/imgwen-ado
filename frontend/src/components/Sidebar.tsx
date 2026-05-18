import { NavLink } from "react-router-dom";

const subLink = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-3 py-2 text-sm ${
    isActive ? "bg-accent/10 font-medium text-accent" : "text-zinc-600 hover:bg-zinc-100"
  }`;

export function Sidebar() {
  return (
    <aside className="flex w-56 shrink-0 flex-col gap-6 border-r border-zinc-200/80 bg-white p-4">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-zinc-400">Current project</p>
        <p className="mt-1 font-semibold text-zinc-900">Spring lookbook</p>
        <p className="text-xs text-zinc-500">Last edited 2h ago</p>
      </div>
      <nav className="flex flex-col gap-1">
        <NavLink to="/workspace" className={subLink} end>
          Assistant
        </NavLink>
        <NavLink to="/workspace/history" className={subLink}>
          Evolution
        </NavLink>
        <NavLink to="/projects" className={subLink}>
          All projects
        </NavLink>
      </nav>
    </aside>
  );
}
