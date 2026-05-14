/**
 * AssetDAG — React Flow DAG visualization for the asset graph.
 *
 * Nodes: rounded rect cards with asset key + status dot.
 * Edges: curved (Bezier).
 *
 * Docs: https://reactflow.dev/api-reference  (reactflow==11.11.4)
 *
 * Selected node gets the glow-selected CSS class (dark theme only per index.css).
 */

import { useMemo, useCallback } from 'react';
import ReactFlow, {
  Background,
  Controls,
  type Node,
  type Edge,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import type { AssetDTO } from '../types';
import { useUIStore } from '../App';

interface Props {
  assets: AssetDTO[];
  /** When true: minimal controls, no background dots, smaller padding (used in dashboard card). */
  constrained?: boolean;
}

const NODE_W = 180;
const NODE_H = 52;

function layoutNodes(assets: AssetDTO[]): { nodes: Node[]; edges: Edge[] } {
  // Simple topological column layout: assets with no deps in column 0,
  // then each dep adds +1 to the depth. Row position is index within column.
  const depthMap: Record<string, number> = {};
  const assetMap = Object.fromEntries(assets.map((a) => [a.key, a]));

  function depth(key: string, visited = new Set<string>()): number {
    if (depthMap[key] !== undefined) return depthMap[key];
    if (visited.has(key)) return 0; // cycle guard
    visited.add(key);
    const a = assetMap[key];
    if (!a || a.deps.length === 0) return (depthMap[key] = 0);
    const d = Math.max(...a.deps.map((dep) => depth(dep, new Set(visited)) + 1));
    return (depthMap[key] = d);
  }

  assets.forEach((a) => depth(a.key));

  const columns: Record<number, string[]> = {};
  Object.entries(depthMap).forEach(([key, d]) => {
    (columns[d] ??= []).push(key);
  });

  const nodes: Node[] = assets.map((a) => {
    const col = depthMap[a.key] ?? 0;
    const row = columns[col]?.indexOf(a.key) ?? 0;
    return {
      id: a.key,
      position: { x: col * (NODE_W + 60), y: row * (NODE_H + 20) },
      data: { label: a.key, schedule: a.schedule },
      style: {
        width: NODE_W,
        height: NODE_H,
        borderRadius: 10,
        display: 'flex',
        alignItems: 'center',
        padding: '0 12px',
        fontSize: 12,
        fontWeight: 600,
        background: 'var(--surface)',
        border: '1.5px solid var(--border)',
        color: 'var(--text)',
        cursor: 'pointer',
      },
    };
  });

  const edges: Edge[] = assets.flatMap((a) =>
    a.deps.map((dep) => ({
      id: `${dep}->${a.key}`,
      source: dep,
      target: a.key,
      type: 'smoothstep',
      animated: false,
      style: { stroke: 'var(--border)', strokeWidth: 1.5 },
    })),
  );

  return { nodes, edges };
}

export default function AssetDAG({ assets, constrained = false }: Props) {
  const { selectedAssetKey, setSelectedAsset } = useUIStore();
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => layoutNodes(assets),
    [assets],
  );

  const [nodes, , onNodesChange] = useNodesState(initNodes);
  const [edges, , onEdgesChange] = useEdgesState(initEdges);

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      setSelectedAsset(node.id === selectedAssetKey ? null : node.id);
    },
    [selectedAssetKey, setSelectedAsset],
  );

  if (assets.length === 0) {
    return (
      <div
        style={{
          flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--muted)', fontSize: 13,
        }}
      >
        No assets to display in the graph.
      </div>
    );
  }

  return (
    <div style={{ flex: 1, position: 'relative', height: constrained ? 280 : undefined }}>
      <ReactFlow
        nodes={nodes.map((n) => ({
          ...n,
          className: n.id === selectedAssetKey ? 'glow-selected' : '',
          style: {
            ...n.style,
            border: n.id === selectedAssetKey
              ? '2px solid var(--accent)'
              : '1.5px solid var(--border)',
          },
        }))}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: constrained ? 0.2 : 0.3 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={!constrained}
        zoomOnScroll={!constrained}
        panOnScroll={!constrained}
        panOnDrag={!constrained}
        preventScrolling={false}
      >
        {!constrained && (
          <Background
            variant={BackgroundVariant.Dots}
            gap={16}
            size={1}
            color="var(--border)"
          />
        )}
        {!constrained && (
          <Controls showInteractive={false} style={{ bottom: 16, right: 16, left: 'unset' }} />
        )}
      </ReactFlow>
    </div>
  );
}
