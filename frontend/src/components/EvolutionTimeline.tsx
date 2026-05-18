import {
  Background,
  type Edge,
  Handle,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";

type MilestoneData = { title: string; date: string; detail: string };
type MilestoneRfNode = Node<MilestoneData, "milestone">;

function MilestoneNode({ data }: NodeProps<MilestoneRfNode>) {
  return (
    <>
      <Handle type="target" position={Position.Top} className="!bg-transparent !border-0" />
      <div className="w-[260px] rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
        <p className="text-xs font-semibold text-accent">{data.date}</p>
        <p className="mt-1 text-sm font-bold text-zinc-900">{data.title}</p>
        <p className="mt-2 text-xs leading-relaxed text-zinc-600">{data.detail}</p>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-transparent !border-0" />
    </>
  );
}

const nodeTypes = { milestone: MilestoneNode };

export function EvolutionTimeline({ className = "" }: { className?: string }) {
  const nodes: MilestoneRfNode[] = useMemo(
    () => [
      {
        id: "m1",
        type: "milestone",
        position: { x: 40, y: 0 },
        data: {
          title: "Concept lock",
          date: "Week 1",
          detail: "Palette and silhouette agreed with the client.",
        },
      },
      {
        id: "m2",
        type: "milestone",
        position: { x: 40, y: 200 },
        data: {
          title: "First refinement pass",
          date: "Week 3",
          detail: "Texture and lighting tuned; two alternates proposed.",
        },
      },
      {
        id: "m3",
        type: "milestone",
        position: { x: 40, y: 400 },
        data: {
          title: "Sign-off",
          date: "Week 5",
          detail: "Hero assets exported for campaign drop.",
        },
      },
    ],
    [],
  );

  const edges: Edge[] = useMemo(
    () => [
      {
        id: "me1",
        source: "m1",
        target: "m2",
        style: { stroke: "#5e5ce6", strokeWidth: 3 },
        type: "smoothstep",
      },
      {
        id: "me2",
        source: "m2",
        target: "m3",
        style: { stroke: "#5e5ce6", strokeWidth: 3 },
        type: "smoothstep",
      },
    ],
    [],
  );

  return (
    <div className={`min-h-[640px] w-full rounded-2xl border border-zinc-200/80 bg-white ${className}`}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          minZoom={0.5}
          maxZoom={1.25}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={16} color="#f4f4f5" />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
