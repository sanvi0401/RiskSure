"use client"

import { useCallback, useEffect, useState } from "react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { apiFetch, API_ENDPOINTS } from "@/lib/api"
import { useAuth } from "@/context/auth-context"
import { RoleGuard } from "@/components/auth/role-guard"
import { Loader2, Network, RefreshCw } from "lucide-react"
import { RelationshipGraphCanvas, type RelationshipGraph } from "@/components/underwriting/relationship-graph-canvas"

const titles: Record<string, { title: string; subtitle: string }> = {
  provider: { title: "Provider Relationship Graph", subtitle: "Claims and relationships connected to your provider account." },
  underwriter: { title: "Case Relationship Graph", subtitle: "Application-scoped relationships authorized for underwriting review." },
  claims_officer: { title: "Claims Relationship Graph", subtitle: "Authorized claim, customer, and provider relationships." },
  admin: { title: "Insurance Relationship Graph", subtitle: "System-wide relationship view available to administrators." },
}

function RelationshipGraphPageContent() {
  const { user } = useAuth()
  const [graph, setGraph] = useState<RelationshipGraph | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [applicationId, setApplicationId] = useState("")
  const [expanding, setExpanding] = useState(false)

  const load = useCallback(async (expandNodeId?: string) => {
    setLoading(true)
    setError("")
    try {
      if (user?.role === "underwriter" && !applicationId) {
        setGraph(null)
        setError("Enter an application ID to view its scoped relationship graph.")
        return
      }
      const query = new URLSearchParams()
      if (user?.role === "underwriter") query.set("application_id", applicationId)
      if (expandNodeId) query.set(user?.role === "admin" ? "expand_node_id" : "expand_node_id", expandNodeId)
      const endpoint = user?.role === "admin" ? API_ENDPOINTS.adminGraph : API_ENDPOINTS.relationshipGraph
      const suffix = query.size ? `?${query.toString()}` : ""
      const response = await apiFetch(`${endpoint}${suffix}`)
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(data?.error || "Unable to load relationship graph")
      setGraph(data as RelationshipGraph)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load relationship graph")
    } finally {
      setLoading(false)
      setExpanding(false)
    }
  }, [applicationId, user?.role])

  useEffect(() => {
    if (typeof window !== "undefined") {
      setApplicationId(new URLSearchParams(window.location.search).get("application_id") ?? "")
    }
  }, [])
  useEffect(() => {
    if (user?.role !== "underwriter" || applicationId) void load()
    else if (user?.role) {
      setLoading(false)
      setError("Enter an application ID to view its scoped relationship graph.")
    }
  }, [user?.role, applicationId, load])

  const meta = titles[user?.role || "admin"]

  return (
    <RoleGuard allowedRoles={["underwriter", "claims_officer", "provider", "admin"]}>
      <DashboardLayout title={meta.title} subtitle={meta.subtitle}>
        <div className="space-y-6">
          <section className="glass-panel rounded-[2rem] p-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-sm font-medium text-primary"><Network className="h-4 w-4" /> Relationship Intelligence</div>
                <p className="mt-2 text-sm text-muted-foreground">The backend enforces your role and entity scope before returning any graph data.</p>
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
              <span className="rounded-full border border-white/10 px-3 py-1.5">Source: {graph?.source ?? "unavailable"}</span>
              <span className="rounded-full border border-white/10 px-3 py-1.5">Neo4j: {graph?.neo4j_configured ? "configured" : "not configured"}</span>
            </div>
          </section>

          {loading ? <div role="status" className="glass-panel flex justify-center rounded-[2rem] p-16"><Loader2 className="animate-spin" /></div>
            : error ? <div role="alert" className="glass-panel rounded-[2rem] p-6 text-destructive">{error}</div>
              : graph && <section className="glass-panel rounded-[2rem] p-6">
                <h2 className="text-xl font-semibold">Relationship Map</h2>
                <p className="mb-5 mt-1 text-sm text-muted-foreground">Drag to reposition and pan, scroll or use controls to zoom, select a node for its details, and expand its direct relationships.</p>
                <RelationshipGraphCanvas
                  graph={graph}
                  expanding={expanding}
                  onExpand={user?.role === "admin" || user?.role === "underwriter" ? (nodeId) => {
                    setExpanding(true)
                    void load(nodeId)
                  } : undefined}
                />
                {graph.edges.length > 0 && <details className="mt-5 rounded-xl border border-white/10 p-4">
                  <summary className="cursor-pointer text-sm font-medium">Relationship records ({graph.edges.length})</summary>
                  <div className="mt-3 max-h-72 space-y-2 overflow-auto">
                    {graph.edges.map((edge, index) => <p key={`${edge.source}-${edge.target}-${index}`} className="text-xs text-muted-foreground">
                      <span className="text-foreground">{edge.source}</span> —{edge.relationship}→ <span className="text-foreground">{edge.target}</span>
                    </p>)}
                  </div>
                </details>}
              </section>}
        </div>
      </DashboardLayout>
    </RoleGuard>
  )
}

export default function RelationshipGraphPage() {
  return <RelationshipGraphPageContent />
}
