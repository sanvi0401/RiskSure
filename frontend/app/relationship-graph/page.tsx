"use client"

import { useEffect, useMemo, useState } from "react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { apiFetch, API_ENDPOINTS } from "@/lib/api"
import { useAuth } from "@/context/auth-context"
import { RoleGuard } from "@/components/auth/role-guard"
import { Loader2, Network, RefreshCw } from "lucide-react"

type GraphNode = { id: string; type: string; properties?: Record<string, unknown> }
type Edge = { source: string; target: string; relationship: string }
type Graph = { source: "neo4j" | "postgres"; neo4j_configured: boolean; nodes: GraphNode[]; edges: Edge[]; claims: unknown[] }

const titles: Record<string, { title: string; subtitle: string }> = {
  customer: { title: "Relationship Graph", subtitle: "Relationship graph access is restricted to authorized staff." },
  provider: { title: "Provider Relationship Graph", subtitle: "Claims and relationships connected to your provider account." },
  underwriter: { title: "Case Relationship Graph", subtitle: "Authorized claim relationships for underwriting review." },
  claims_officer: { title: "Claims Relationship Graph", subtitle: "Authorized claim, customer, and provider relationships." },
  admin: { title: "Insurance Relationship Graph", subtitle: "System-wide relationship view available to administrators." },
}

export default function RelationshipGraphPage() {
  const { user } = useAuth()
  const [graph, setGraph] = useState<Graph | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [applicationId, setApplicationId] = useState("")
  const [search, setSearch] = useState("")
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const load = async () => {
    setLoading(true); setError("")
    try {
      if (user?.role === "underwriter" && !applicationId) {
        setGraph(null)
        setError("Enter an application ID to view its scoped relationship graph.")
        return
      }
      const endpoint = user?.role === "underwriter"
        ? `${API_ENDPOINTS.relationshipGraph}?application_id=${encodeURIComponent(applicationId)}`
        : API_ENDPOINTS.relationshipGraph
      const response = await apiFetch(endpoint)
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(data?.error || "Unable to load relationship graph")
      setGraph(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load relationship graph")
    } finally { setLoading(false) }
  }

  useEffect(() => {
    if (typeof window !== "undefined") {
      setApplicationId(new URLSearchParams(window.location.search).get("application_id") ?? "")
    }
  }, [])
  useEffect(() => {
    if (user?.role !== "underwriter" || applicationId) void load()
  }, [user?.role, applicationId])

  const meta = titles[user?.role || "customer"]
  const nodeRows = useMemo(() => graph?.nodes ?? [], [graph])
  const edgeRows = useMemo(() => graph?.edges ?? [], [graph])
  const positions = useMemo(() => nodeRows.map((node, index) => {
    const angle = (2 * Math.PI * index) / Math.max(nodeRows.length, 1) - Math.PI / 2
    return { node, x: 400 + Math.cos(angle) * Math.min(250, 100 + nodeRows.length * 12), y: 240 + Math.sin(angle) * Math.min(170, 70 + nodeRows.length * 9) }
  }), [nodeRows])
  const positionById = useMemo(() => new Map(positions.map((item) => [item.node.id, item])), [positions])
  const matchesSearch = (node: GraphNode) => !search.trim()
    || `${node.id} ${node.type} ${JSON.stringify(node.properties ?? {})}`.toLowerCase().includes(search.toLowerCase())
  const selectedNode = nodeRows.find((node) => node.id === selectedNodeId)

  return (
    <RoleGuard allowedRoles={["underwriter", "claims_officer", "provider", "admin"]}>
    <DashboardLayout title={meta.title} subtitle={meta.subtitle}>
      <div className="space-y-6">
        <div className="glass-panel rounded-[2rem] p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-sm font-medium text-primary">
                <Network className="h-4 w-4" /> Relationship Intelligence
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                The graph is read through the RiskSure backend. Your role controls which relationships can be returned.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
            {user?.role === "underwriter" && <input aria-label="Application ID" inputMode="numeric" value={applicationId} onChange={(event) => setApplicationId(event.target.value.replace(/\D/g, ""))} placeholder="Application ID" className="w-36 rounded-2xl border border-white/10 bg-background px-3 py-2 text-sm" />}
            <button onClick={() => void load()} disabled={loading} className="inline-flex items-center gap-2 rounded-2xl border border-white/10 px-4 py-2 text-sm hover:bg-white/5 disabled:opacity-50">
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            </div>
          </div>
          <div className="mt-5 flex flex-wrap gap-3 text-xs">
            <span className="rounded-full border border-white/10 px-3 py-1.5">Role: {user?.role ?? "unknown"}</span>
            <span className="rounded-full border border-white/10 px-3 py-1.5">Source: {graph?.source ?? "loading"}</span>
            <span className="rounded-full border border-white/10 px-3 py-1.5">Neo4j: {graph?.neo4j_configured ? "configured" : "not configured"}</span>
          </div>
        </div>

        {loading ? (
          <div className="glass-panel flex justify-center rounded-[2rem] p-16"><Loader2 className="animate-spin" /></div>
        ) : error ? (
          <div className="glass-panel rounded-[2rem] p-6 text-destructive">{error}</div>
        ) : (
          <>
            <div className="glass-panel rounded-[2rem] p-6">
              <h2 className="text-xl font-semibold">Relationship Map</h2>
              <p className="mt-1 text-sm text-muted-foreground">Nodes represent entities; edges represent relationships returned by Neo4j or the safe PostgreSQL fallback.</p>
              <input value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Search graph nodes" placeholder="Search nodes" className="mt-4 w-full rounded-xl border border-white/10 bg-background px-3 py-2 text-sm md:max-w-sm" />
              {nodeRows.length === 0 ? (
                <p className="py-12 text-center text-muted-foreground">No relationship data is available yet. Submit or process a claim to populate the graph.</p>
              ) : (
                <svg role="img" aria-label="Interactive relationship graph" viewBox="0 0 800 480" className="mt-5 h-[420px] w-full rounded-2xl border border-white/10 bg-black/10">
                  {edgeRows.map((edge, index) => {
                    const source = positionById.get(edge.source)
                    const target = positionById.get(edge.target)
                    if (!source || !target) return null
                    return <g key={`${edge.source}-${edge.target}-${index}`} className="text-muted-foreground">
                      <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="currentColor" strokeOpacity="0.45" strokeWidth="2" />
                      <title>{edge.relationship}</title>
                    </g>
                  })}
                  {positions.map(({ node, x, y }) => (
                    <g key={node.id} role="button" tabIndex={0} aria-label={`${node.type}: ${node.id}`} aria-pressed={selectedNodeId === node.id}
                      onClick={() => setSelectedNodeId(node.id)}
                      onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") setSelectedNodeId(node.id) }}
                      opacity={matchesSearch(node) ? 1 : 0.2} className="cursor-pointer">
                      <circle cx={x} cy={y} r={selectedNodeId === node.id ? 38 : 31} fill="hsl(var(--primary))" fillOpacity="0.85" stroke="hsl(var(--foreground))" strokeOpacity="0.7" />
                      <text x={x} y={y + 4} textAnchor="middle" fill="white" fontSize="10">{node.type}</text>
                      <text x={x} y={y + 52} textAnchor="middle" fill="currentColor" fontSize="10">{node.id}</text>
                    </g>
                  ))}
                </svg>
              )}
              {selectedNode && <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-4"><p className="font-medium">{selectedNode.type}: {selectedNode.id}</p><pre className="mt-2 whitespace-pre-wrap break-words text-xs text-muted-foreground">{JSON.stringify(selectedNode.properties ?? {}, null, 2)}</pre></div>}
            </div>
            <div className="glass-panel rounded-[2rem] p-6">
              <h2 className="text-xl font-semibold">Connections</h2>
              {edgeRows.length === 0 ? (
                <p className="py-8 text-muted-foreground">No connections found.</p>
              ) : (
                <div className="mt-4 space-y-2">
                  {edgeRows.map((edge, index) => (
                    <div key={index} className="flex flex-wrap items-center gap-2 rounded-xl border border-white/10 px-4 py-3 text-sm">
                      <span>{edge.source}</span><span className="text-primary">— {edge.relationship} →</span><span>{edge.target}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
    </RoleGuard>
  )
}
