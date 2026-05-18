import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";

export function WorkspaceLayout() {
  return (
    <div className="flex min-h-[calc(100vh-4rem)] w-full">
      <Sidebar />
      <div className="min-w-0 flex-1">
        <Outlet />
      </div>
    </div>
  );
}
