import {
  Background,
  Controls,
  type Edge,
  Handle,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import { HardDrive, Lock } from 'lucide-react'
import { useMemo } from 'react'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { LineageGraphResponse, LineageNode } from '@/types/lineage'

interface LineageGraphProps {
  data: LineageGraphResponse
}

interface TableNodeData extends Record<string, unknown> {
  projectId: string
  datasetId: string
  tableId: string
  isRoot: boolean
  accessDenied: boolean
}

interface BucketNodeData extends Record<string, unknown> {
  bucketName: string
}

type GraphNode = Node<TableNodeData> | Node<BucketNodeData>

const NODE_WIDTH = 220
const NODE_HEIGHT = 56

function buildBucketNode(n: LineageNode): Node<BucketNodeData> {
  return {
    id: n.id,
    type: 'bucketNode',
    position: { x: 0, y: 0 },
    data: { bucketName: n.bucket_name ?? '' },
  }
}

function buildElements(data: LineageGraphResponse): {
  nodes: GraphNode[]
  edges: Edge[]
} {
  const rootId = `${data.root.project_id}:${data.root.dataset_id}:${data.root.table_id}`

  const nodes: GraphNode[] = [
    {
      id: rootId,
      type: 'tableNode',
      position: { x: 0, y: 0 },
      data: {
        projectId: data.root.project_id,
        datasetId: data.root.dataset_id,
        tableId: data.root.table_id,
        isRoot: true,
        accessDenied: false,
      },
    },
    ...data.nodes.map((n): GraphNode => {
      if (n.type === 'bucket') return buildBucketNode(n)
      return {
        id: n.id,
        type: 'tableNode',
        position: { x: 0, y: 0 },
        data: {
          projectId: n.project_id ?? '',
          datasetId: n.dataset_id ?? '',
          tableId: n.table_id ?? '',
          isRoot: false,
          accessDenied: n.access_denied,
        },
      }
    }),
  ]

  const edges: Edge[] = data.edges.map((e) => ({
    id: `${e.source}->${e.target}`,
    source: e.source,
    target: e.target,
  }))

  return { nodes, edges }
}

function layout(nodes: GraphNode[], edges: Edge[]): GraphNode[] {
  const graph = new dagre.graphlib.Graph()
  graph.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 80 })
  graph.setDefaultEdgeLabel(() => ({}))

  for (const node of nodes) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }
  for (const edge of edges) {
    graph.setEdge(edge.source, edge.target)
  }

  dagre.layout(graph)

  return nodes.map((node) => {
    const position = graph.node(node.id)
    return {
      ...node,
      position: { x: position.x - NODE_WIDTH / 2, y: position.y - NODE_HEIGHT / 2 },
    }
  })
}

function LineageTableNode({ data }: NodeProps<Node<TableNodeData>>) {
  const label = `${data.projectId}.${data.datasetId}.${data.tableId}`

  const node = (
    <div
      style={{ width: NODE_WIDTH }}
      className={cn(
        'flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs',
        data.isRoot ? 'border-primary bg-primary/10 font-semibold' : 'border-border bg-card',
        data.accessDenied && 'cursor-not-allowed border-dashed text-muted-foreground opacity-50',
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground" />
      {data.accessDenied && <Lock size={12} className="shrink-0" />}
      <span className="truncate">{label}</span>
      <Handle type="source" position={Position.Right} className="!bg-muted-foreground" />
    </div>
  )

  if (!data.accessDenied) return node

  return (
    <Tooltip>
      <TooltipTrigger render={node} />
      <TooltipContent>Acesso não concedido a este projeto</TooltipContent>
    </Tooltip>
  )
}

// Bucket é sempre folha no grafo (nunca é root, nunca access_denied — ver
// docs/specs/storage.md seção 7.2) — estilo visualmente distinto (ícone +
// cor) reaproveitando a identidade do grupo "Cloud Storage" da sidebar.
function LineageBucketNode({ data }: NodeProps<Node<BucketNodeData>>) {
  return (
    <div
      style={{ width: NODE_WIDTH }}
      className="flex items-center gap-1.5 rounded-lg border border-status-ok/30 bg-status-ok/10 px-3 py-2 text-xs"
    >
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground" />
      <HardDrive size={12} className="shrink-0" />
      <span className="truncate">{data.bucketName}</span>
      <Handle type="source" position={Position.Right} className="!bg-muted-foreground" />
    </div>
  )
}

const nodeTypes = { tableNode: LineageTableNode, bucketNode: LineageBucketNode }

export function LineageGraph({ data }: LineageGraphProps) {
  const { nodes, edges } = useMemo(() => {
    const { nodes: rawNodes, edges: rawEdges } = buildElements(data)
    return { nodes: layout(rawNodes, rawEdges), edges: rawEdges }
  }, [data])

  return (
    <div className="h-[480px] overflow-hidden rounded-lg border border-border bg-card">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        nodesConnectable={false}
        edgesReconnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}
