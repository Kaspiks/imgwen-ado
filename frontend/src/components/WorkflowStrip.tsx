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

type PillData = { label: string };
type PillRfNode = Node<PillData, "pill">;

function PillNode({ data }: NodeProps<PillRfNode>) {
  return (
    <>
      <Handle type="target" position={Position.Left} className="!bg-accent !border-0 !w-2 !h-2" />
      <div className="rounded-full border border-zinc-200 bg-white px-4 py-2 text-xs font-semibold text-zinc-800 shadow-sm">
        {data.label}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-accent !border-0 !w-2 !h-2" />
    </>
  );
}

const nodeTypes = { pill: PillNode };

export function WorkflowStrip({ className = "" }: { className?: string }) {
  const nodes: PillRfNode[] = useMemo(
    () => [
      { id: "1", type: "pill", position: { x: 0, y: 24 }, data: { label: "Analyze" } },
      { id: "2", type: "pill", position: { x: 140, y: 24 }, data: { label: "Suggest" } },
      { id: "3", type: "pill", position: { x: 280, y: 24 }, data: { label: "Choose" } },
      { id: "4", type: "pill", position: { x: 420, y: 24 }, data: { label: "Edit" } },
    ],
    [],
  );

  const edges: Edge[] = useMemo(
    () => [
      { id: "e1-2", source: "1", target: "2", animated: true, style: { stroke: "#5e5ce6" } },
      { id: "e2-3", source: "2", target: "3", animated: true, style: { stroke: "#5e5ce6" } },
      { id: "e3-4", source: "3", target: "4", animated: true, style: { stroke: "#5e5ce6" } },
    ],
    [],
  );

  return (
    <div className={`h-28 w-full overflow-hidden rounded-2xl border border-zinc-200/80 bg-white ${className}`}>
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          preventScrolling
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={12} color="#e4e4e7" />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
