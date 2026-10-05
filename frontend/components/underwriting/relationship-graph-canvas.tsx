"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Maximize2, Minus, Plus, RotateCcw } from "lucide-react"
import { Button } from "@/components/ui/button"

export type GraphNode = { id: string; type: string; properties?: Record<string, unknown> }
export type GraphEdge = { source: string; target: string; relationship: string }
export type RelationshipGraph = {
  source: string
  neo4j_configured: boolean
  nodes: GraphNode[]
  edges: GraphEdge[]
}

type Point = { x: number; y: number }
type View = { x: number; y: number; scale: number }
type DragState = { pointerId: number; nodeId?: string; lastX: number; lastY: number }

const canvasWidth = 800
const canvasHeight = 480
const colors: Record<string, string> = {
  customer: "#0ea5e9",
  application: "#8b5cf6",
  riskfactor: "#f59e0b",
  claim: "#ef4444",
  policy: "#10b981",
  underwriter: "#6366f1",
  decision: "#14b8a6",
  location: "#64748b",
  provider: "#ec4899",
}

function nodeLabel(node: GraphNode): string {
  const props = node.properties ?? {}
  return String(props.name ?? props.policy_number ?? props.claim_number ?? props.value ?? node.id)
}

function initialPositions(nodes: GraphNode[]): Record<string, Point> {
  const centerX = canvasWidth / 2
  const centerY = canvasHeight / 2
  const radiusX = Math.min(300, 100 + nodes.length * 12)
  const radiusY = Math.min(190, 65 + nodes.length * 8)
  return Object.fromEntries(nodes.map((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(nodes.length, 1) - Math.PI / 2
    return [node.id, { x: centerX + Math.cos(angle) * radiusX, y: centerY + Math.sin(angle) * radiusY }]
  }))
}

export function RelationshipGraphCanvas({
  graph,
  onExpand,
  expanding = false,
}: {
  graph: RelationshipGraph
  onExpand?: (nodeId: string) => void
  expanding?: boolean
}) {
  const svgRef = useRef<SVGSVGElement>(null)
  const dragRef = useRef<DragState | null>(null)
  const [positions, setPositions] = useState<Record<string, Point>>(() => initialPositions(graph.nodes))
  const [view, setView] = useState<View>({ x: 0, y: 0, scale: 1 })
  const [search, setSearch] = useState("")
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  useEffect(() => {
    setPositions(initialPositions(graph.nodes))
    setSelectedNodeId(null)
    setView({ x: 0, y: 0, scale: 1 })
  }, [graph])

  const positionsById = useMemo(() => {
    const current = { ...positions }
    for (const node of graph.nodes) {
      if (!current[node.id]) current[node.id] = initialPositions([node])[node.id]
    }
    return current
  }, [graph.nodes, positions])
  const selectedNode = graph.nodes.find((node) => node.id === selectedNodeId) ?? null
  const normalizedSearch = search.trim().toLowerCase()
  const matches = (node: GraphNode) => !normalizedSearch
    || `${node.id} ${node.type} ${JSON.stringify(node.properties ?? {})}`.toLowerCase().includes(normalizedSearch)

  const localPoint = (event: React.PointerEvent<SVGSVGElement | SVGGElement>) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const point = svg.createSVGPoint()
    point.x = event.clientX
    point.y = event.clientY
    const matrix = svg.getScreenCTM()
    const local = matrix ? point.matrixTransform(matrix.inverse()) : point
    return { x: local.x, y: local.y }
  }

  const worldPoint = (event: React.PointerEvent<SVGSVGElement | SVGGElement>) => {
    const point = localPoint(event)
    return { x: (point.x - view.x) / view.scale, y: (point.y - view.y) / view.scale }
  }

  const zoom = (factor: number, focus = { x: canvasWidth / 2, y: canvasHeight / 2 }) => {
    setView((current) => {
      const scale = Math.min(3, Math.max(0.35, current.scale * factor))
      return {
        scale,
        x: focus.x - (focus.x - current.x) * scale / current.scale,
        y: focus.y - (focus.y - current.y) * scale / current.scale,
      }
    })
  }

  const fitView = () => {
    const points = graph.nodes.map((node) => positionsById[node.id]).filter((point): point is Point => Boolean(point))
    if (!points.length) {
      setView({ x: 0, y: 0, scale: 1 })
      return
    }
    const minX = Math.min(...points.map((point) => point.x)) - 55
    const maxX = Math.max(...points.map((point) => point.x)) + 55
    const minY = Math.min(...points.map((point) => point.y)) - 55
    const maxY = Math.max(...points.map((point) => point.y)) + 55
    const scale = Math.min(1.5, canvasWidth / (maxX - minX), canvasHeight / (maxY - minY))
    setView({
      scale,
      x: (canvasWidth - (minX + maxX) * scale) / 2,
      y: (canvasHeight - (minY + maxY) * scale) / 2,
    })
  }

  const handleWheel = (event: React.WheelEvent<SVGSVGElement>) => {
    event.preventDefault()
    const bounds = event.currentTarget.getBoundingClientRect()
    const focus = {
      x: (event.clientX - bounds.left) * canvasWidth / bounds.width,
      y: (event.clientY - bounds.top) * canvasHeight / bounds.height,
    }
    zoom(event.deltaY < 0 ? 1.1 : 0.9, focus)
  }

  const handlePointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    if (drag.nodeId) {
      const point = worldPoint(event)
      setPositions((current) => ({ ...current, [drag.nodeId as string]: point }))
    } else {
      const bounds = event.currentTarget.getBoundingClientRect()
      const dx = (event.clientX - drag.lastX) * canvasWidth / bounds.width
      const dy = (event.clientY - drag.lastY) * canvasHeight / bounds.height
      setView((current) => ({ ...current, x: current.x + dx, y: current.y + dy }))
      drag.lastX = event.clientX
      drag.lastY = event.clientY
    }
  }

  const endPointer = (event: React.PointerEvent<SVGSVGElement>) => {
    if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          aria-label="Search graph nodes"
          placeholder="Search entities in this graph"
          className="w-full rounded-xl border border-white/10 bg-background px-3 py-2 text-sm md:max-w-sm"
        />
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => zoom(1.2)} aria-label="Zoom in"><Plus className="h-4 w-4" /></Button>
          <Button type="button" variant="outline" size="sm" onClick={() => zoom(1 / 1.2)} aria-label="Zoom out"><Minus className="h-4 w-4" /></Button>
          <Button type="button" variant="outline" size="sm" onClick={fitView}><Maximize2 className="mr-2 h-4 w-4" />Fit</Button>
          <Button type="button" variant="outline" size="sm" onClick={() => setView({ x: 0, y: 0, scale: 1 })}><RotateCcw className="mr-2 h-4 w-4" />Reset</Button>
        </div>
      </div>

      {!graph.nodes.length ? (
        <div className="rounded-2xl border border-dashed border-white/15 px-6 py-14 text-center text-sm text-muted-foreground">
          No relationship data is available for this scope yet.
        </div>
      ) : (
        <svg
          ref={svgRef}
          role="img"
          aria-label="Interactive relationship graph. Drag nodes to reposition; drag the background to pan and use the mouse wheel to zoom."
          viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}
          onWheel={handleWheel}
          onPointerDown={(event) => {
            if (event.target instanceof Element && event.target.closest('[role="button"]')) return
            dragRef.current = { pointerId: event.pointerId, lastX: event.clientX, lastY: event.clientY }
            event.currentTarget.setPointerCapture(event.pointerId)
          }}
          onPointerMove={handlePointerMove}
          onPointerUp={endPointer}
          onPointerCancel={endPointer}
          className="h-[420px] w-full touch-none rounded-2xl border border-white/10 bg-black/10"
        >
          <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
            {graph.edges.map((edge, index) => {
              const source = positionsById[edge.source]
              const target = positionsById[edge.target]
              if (!source || !target) return null
              return <g key={`${edge.source}-${edge.target}-${edge.relationship}-${index}`} className="pointer-events-none">
                <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="currentColor" strokeOpacity="0.4" strokeWidth="2" />
                <text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 5} textAnchor="middle" fill="currentColor" fontSize="10" paintOrder="stroke" stroke="hsl(var(--background))" strokeWidth="4">
                  {edge.relationship.replaceAll("_", " ")}
                </text>
              </g>
            })}
            {graph.nodes.map((node) => {
              const point = positionsById[node.id]
              if (!point) return null
              const selected = selectedNodeId === node.id
              return <g
                key={node.id}
                role="button"
                tabIndex={0}
                aria-label={`${node.type}: ${nodeLabel(node)}`}
                aria-pressed={selected}
                onClick={() => setSelectedNodeId(node.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault()
                    setSelectedNodeId(node.id)
                  }
                }}
                onPointerDown={(event) => {
                  event.stopPropagation()
                  event.currentTarget.setPointerCapture(event.pointerId)
                  setSelectedNodeId(node.id)
                  dragRef.current = { pointerId: event.pointerId, nodeId: node.id, lastX: event.clientX, lastY: event.clientY }
                }}
                onPointerUp={(event) => {
                  if (dragRef.current?.pointerId === event.pointerId) dragRef.current = null
                }}
                opacity={matches(node) ? 1 : 0.2}
                className="cursor-pointer outline-none"
              >
                <circle cx={point.x} cy={point.y} r={selected ? 35 : 29} fill={colors[node.type.toLowerCase()] ?? "#64748b"} fillOpacity="0.9" stroke={selected ? "white" : "hsl(var(--foreground))"} strokeOpacity="0.8" strokeWidth={selected ? 3 : 1.5} />
                <text x={point.x} y={point.y + 4} textAnchor="middle" fill="white" fontSize="10" pointerEvents="none">{node.type}</text>
                <text x={point.x} y={point.y + 45} textAnchor="middle" fill="currentColor" fontSize="10" pointerEvents="none">{nodeLabel(node).slice(0, 32)}</text>
              </g>
            })}
          </g>
        </svg>
      )}

      {selectedNode && <aside aria-label="Selected node details" className="rounded-xl border border-primary/20 bg-primary/5 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="font-medium">{selectedNode.type}: {nodeLabel(selectedNode)}</p><p className="text-xs text-muted-foreground">{selectedNode.id}</p></div>
          {onExpand && <Button type="button" size="sm" variant="outline" onClick={() => onExpand(selectedNode.id)} disabled={expanding}>
            {expanding ? "Expanding…" : "Expand relationships"}
          </Button>}
        </div>
        <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground">{JSON.stringify(selectedNode.properties ?? {}, null, 2)}</pre>
      </aside>}

      <div aria-label="Graph legend" className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        {Object.entries(colors).map(([type, color]) => <span key={type} className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />{type}
        </span>)}
      </div>
    </div>
  )
}
