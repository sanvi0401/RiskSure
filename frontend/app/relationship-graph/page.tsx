"use client"

import { useEffect, useMemo, useState } from "react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { apiFetch, API_ENDPOINTS } from "@/lib/api"
import { useAuth } from "@/context/auth-context"
import { Loader2, Network, RefreshCw } from "lucide-react"

type Node = { id: string; type: string; properties?: Record<string, unknown> }
type Edge = { source: string; target: string; relationship: string }
type Graph = { source: "neo4j" | "postgres"; neo4j_configured: boolean; nodes: Node[]; edges: Edge[]; claims: unknown[] }

const titles: Record<string, { title: string; subtitle: string }> = {
  customer: { title: "My Claim Network", subtitle: "Your claims and their authorized customer/provider relationships." },
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

  const load = async () => {
    setLoading(true); setError("")
    try {
      const response = await apiFetch(API_ENDPOINTS.relationshipGraph)
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(data?.error || "Unable to load relationship graph")
      setGraph(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load relationship graph")
    } finally { setLoading(false) }
  }

  useEffect(() => { void load() }, [])

  const meta = titles[user?.role || "customer"]
  const nodeRows = useMemo(() => graph?.nodes ?? [], [graph])
  const edgeRows = useMemo(() => graph?.edges ?? [], [graph])

  return (
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
            <button onClick={() => void load()} disabled={loading} className="inline-flex items-center gap-2 rounded-2xl border border-white/10 px-4 py-2 text-sm hover:bg-white/5 disabled:opacity-50">
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
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
              {nodeRows.length === 0 ? (
                <p className="py-12 text-center text-muted-foreground">No relationship data is available yet. Submit or process a claim to populate the graph.</p>
              ) : (
                <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {nodeRows.map(node => (
                    <div key={node.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs uppercase tracking-[0.16em] text-primary">{node.type}</span>
                        <span className="text-xs text-muted-foreground">{node.id}</span>
                      </div>
                      <pre className="mt-3 max-h-28 overflow-auto whitespace-pre-wrap break-words text-xs text-muted-foreground">{JSON.stringify(node.properties ?? {}, null, 2)}</pre>
                    </div>
                  ))}
                </div>
              )}
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
  )
}
