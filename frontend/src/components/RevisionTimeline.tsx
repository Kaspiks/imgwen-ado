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

type RevData = { label: string; sub?: string };
type RevRfNode = Node<RevData, "rev">;

function RevNode({ data }: NodeProps<RevRfNode>) {
  return (
    <>
      <Handle type="target" position={Position.Top} className="!bg-accent !border-0 !w-2 !h-2" />
      <div className="w-[100px] rounded-xl border border-zinc-200 bg-white px-2 py-1.5 text-center shadow-sm">
        <p className="text-[10px] font-bold text-zinc-900">{data.label}</p>
        {data.sub ? <p className="text-[9px] text-zinc-500">{data.sub}</p> : null}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-accent !border-0 !w-2 !h-2" />
    </>
  );
}

const nodeTypes = { rev: RevNode };

export function RevisionTimeline({ className = "" }: { className?: string }) {
  const nodes: RevRfNode[] = useMemo(
    () => [
      { id: "r1", type: "rev", position: { x: 24, y: 0 }, data: { label: "v1", sub: "Initial" } },
      { id: "r2", type: "rev", position: { x: 24, y: 72 }, data: { label: "v2", sub: "Tweak" } },
      { id: "r3", type: "rev", position: { x: 24, y: 144 }, data: { label: "v3", sub: "Final" } },
    ],
    [],
  );

  const edges: Edge[] = useMemo(
    () => [
      { id: "re1", source: "r1", target: "r2", style: { stroke: "#5e5ce6", strokeWidth: 2 } },
      { id: "re2", source: "r2", target: "r3", style: { stroke: "#5e5ce6", strokeWidth: 2 } },
    ],
    [],
  );

  return (
    <div className={`h-[220px] w-[140px] shrink-0 overflow-hidden rounded-2xl border border-zinc-200/80 bg-zinc-50 ${className}`}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={false}
          zoomOnScroll={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={10} color="#e4e4e7" />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
