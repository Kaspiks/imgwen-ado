import { Outlet } from "react-router-dom";
import { TopNav } from "./TopNav";

export function AppShell() {
  return (
    <div className="flex min-h-screen flex-col bg-[#f4f4f7]">
      <TopNav />
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
