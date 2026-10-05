"use client"

import { useCallback, useEffect, useState } from "react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { RelationshipGraphCanvas, type RelationshipGraph } from "@/components/underwriting/relationship-graph-canvas"
import { apiJson, API_ENDPOINTS } from "@/lib/api"
import { Button } from "@/components/ui/button"

const entityTypes = ["", "customer", "application", "riskfactor", "claim", "policy", "underwriter", "decision", "provider", "location"]

function AdminGraphExplorer() {
  const [graph, setGraph] = useState<RelationshipGraph | null>(null)
  const [searchText, setSearchText] = useState("")
  const [entityType, setEntityType] = useState("")
  const [loading, setLoading] = useState(true)
  const [expanding, setExpanding] = useState(false)
  const [error, setError] = useState("")

  const loadGraph = useCallback(async (options: { search?: string; type?: string; expandNodeId?: string } = {}) => {
    setLoading(true)
    setError("")
    const query = new URLSearchParams()
    if (options.search) query.set("search", options.search)
    if (options.type) query.set("type", options.type)
    if (options.expandNodeId) query.set("expand_node_id", options.expandNodeId)
    try {
      const suffix = query.size ? `?${query.toString()}` : ""
      setGraph(await apiJson<RelationshipGraph>(`${API_ENDPOINTS.adminGraph}${suffix}`))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load the system graph")
    } finally {
      setLoading(false)
      setExpanding(false)
    }
  }, [])

  useEffect(() => { void loadGraph() }, [loadGraph])

  const search = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void loadGraph({ search: searchText.trim(), type: entityType })
  }

  return (
    <DashboardLayout title="System Relationship Graph" subtitle="Administrator-only investigation across RiskSure entities and their persisted relationships">
      <div className="space-y-6">
        <section className="glass-panel rounded-[2rem] p-6">
          <form onSubmit={search} className="flex flex-wrap items-end gap-3">
            <label className="min-w-[220px] flex-1 text-sm font-medium">
              Search entities
              <input value={searchText} onChange={(event) => setSearchText(event.target.value)} maxLength={160} placeholder="Customer, application, claim, policy ID…" className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-background px-3 text-sm font-normal" />
            </label>
            <label className="text-sm font-medium">
              Entity type
              <select value={entityType} onChange={(event) => setEntityType(event.target.value)} className="mt-2 h-11 rounded-xl border border-white/10 bg-background px-3 text-sm font-normal">
                {entityTypes.map((type) => <option key={type} value={type}>{type ? type.replaceAll("_", " ") : "All types"}</option>)}
              </select>
            </label>
            <Button type="submit" disabled={loading}>{loading ? "Searching…" : "Search graph"}</Button>
            <Button type="button" variant="outline" onClick={() => { setSearchText(""); setEntityType(""); void loadGraph() }} disabled={loading}>Reset</Button>
          </form>
          <div className="mt-4 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span className="rounded-full border border-white/10 px-3 py-1.5">Source: {graph?.source ?? "loading"}</span>
            <span className="rounded-full border border-white/10 px-3 py-1.5">Entities: {graph?.nodes.length ?? 0}</span>
            <span className="rounded-full border border-white/10 px-3 py-1.5">Relationships: {graph?.edges.length ?? 0}</span>
            <span className="rounded-full border border-white/10 px-3 py-1.5">Neo4j: {graph?.neo4j_configured ? "configured" : "not configured"}</span>
          </div>
        </section>

        {error && <div role="alert" className="rounded-2xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">{error}</div>}
        {loading && !graph ? <div role="status" className="glass-panel rounded-[2rem] p-10 text-center">Loading the system graph…</div>
          : graph && <section className="glass-panel rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Graph investigation</h2>
            <p className="mb-5 mt-1 text-sm text-muted-foreground">Select an entity to inspect its stored properties, then expand its direct connections. Results are bounded and no Cypher is exposed to the browser.</p>
            <RelationshipGraphCanvas
              graph={graph}
              expanding={expanding}
              onExpand={(nodeId) => {
                setExpanding(true)
                void loadGraph({ expandNodeId: nodeId })
              }}
            />
            {graph.edges.length > 0 && <details className="mt-5 rounded-xl border border-white/10 p-4">
              <summary className="cursor-pointer text-sm font-medium">Inspect relationship records ({graph.edges.length})</summary>
              <div className="mt-3 max-h-72 space-y-2 overflow-auto">
                {graph.edges.map((edge, index) => <p key={`${edge.source}-${edge.target}-${index}`} className="text-xs text-muted-foreground">
                  <span className="text-foreground">{edge.source}</span> —{edge.relationship}→ <span className="text-foreground">{edge.target}</span>
                </p>)}
              </div>
            </details>}
          </section>}
      </div>
    </DashboardLayout>
  )
}

export default function AdminGraphPage() {
  return <RoleGuard allowedRoles={["admin"]}><AdminGraphExplorer /></RoleGuard>
}
