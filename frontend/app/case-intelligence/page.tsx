"use client"

import { Suspense, useCallback, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { apiJson, API_ENDPOINTS } from "@/lib/api"

interface CaseEvidence {
  application: {
    id: number
    name: string
    review_status: string
    decision: string
    decision_reason: string | null
  }
  risk: {
    risk_score: number
    final_risk: number
    risk_category: string
    premium: number
    decision: string
    model_version: string
    prediction_timestamp: string
    important_features: { feature: string; importance: number; evidence_type: string }[]
    rule_factors: { feature: string; adjustment: number }[]
    warnings: string[]
  }
  statistics: {
    sample_size: number
    risk_distribution: Record<string, number>
    risk_score_summary: { mean: number | null; median: number | null }
    risk_groups: Record<string, { count: number; mean_risk: number | null; mean_premium: number | null }>
    subject_comparison: { risk_category: string; cohort_size: number; cohort_mean_risk: number | null } | null
    outliers: { feature: string; value: number; method: string }[]
    correlations: Record<string, number>
    limitations: string[]
  }
  graph_evidence: {
    source: string
    neo4j_configured: boolean
    nodes: { id: string; type: string; properties: Record<string, unknown> }[]
    edges: { source: string; target: string; relationship: string }[]
  }
  policy_evidence: { text: string; section: number | null; source: string; retrieval: string }[]
  claims: { id: number; claim_number: string; status: string; claimed_amount: number }[]
  human_review_required: boolean
  ai_explanation: { available: boolean; summary: string | null; warning: string; human_decision_required: boolean }
}

function EvidenceCard({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="glass-panel rounded-[2rem] p-6">
    <h2 className="text-xl font-semibold">{title}</h2>
    <div className="mt-4">{children}</div>
  </section>
}

function CaseIntelligence() {
  const params = useSearchParams()
  const rawId = params.get("id")
  const applicationId = rawId && /^\d+$/.test(rawId) ? Number(rawId) : null
  const [evidence, setEvidence] = useState<CaseEvidence | null>(null)
  const [loading, setLoading] = useState(true)
  const [assistantLoading, setAssistantLoading] = useState(false)
  const [error, setError] = useState("")
  const [assistantError, setAssistantError] = useState("")
  const [question, setQuestion] = useState("What risk factors and policy terms should be investigated?")

  const load = useCallback(async () => {
    if (!applicationId) {
      setError("A valid application ID is required.")
      setLoading(false)
      return
    }
    setLoading(true)
    setError("")
    try {
      setEvidence(await apiJson<CaseEvidence>(API_ENDPOINTS.caseIntelligence(applicationId)))
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load case intelligence")
    } finally {
      setLoading(false)
    }
  }, [applicationId])

  useEffect(() => { void load() }, [load])

  const requestAssistant = async () => {
    if (!applicationId) return
    setAssistantLoading(true)
    setAssistantError("")
    try {
      const result = await apiJson<CaseEvidence["ai_explanation"] & { application_id: number }>(
        API_ENDPOINTS.caseAssistant(applicationId),
        { method: "POST", body: JSON.stringify({ question }) },
      )
      setEvidence((current) => current ? { ...current, ai_explanation: result } : current)
    } catch (requestError) {
      setAssistantError(requestError instanceof Error ? requestError.message : "Unable to request assistant analysis")
    } finally {
      setAssistantLoading(false)
    }
  }

  return (
    <DashboardLayout title="Underwriting Case Intelligence" subtitle="Evidence from the stored risk assessment, application cohort, relationships, and policy documents">
      {loading ? <div role="status" className="glass-panel rounded-[2rem] p-10 text-center">Loading application evidence…</div>
        : error ? <div role="alert" className="glass-panel rounded-[2rem] p-6 text-destructive">{error}</div>
          : evidence ? <div className="space-y-6">
            <EvidenceCard title={`Application #${evidence.application.id}: ${evidence.application.name}`}>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><p className="text-xs text-muted-foreground">RISK CATEGORY</p><b>{evidence.risk.risk_category}</b></div>
                <div><p className="text-xs text-muted-foreground">FINAL RISK</p><b>{(evidence.risk.final_risk * 100).toFixed(1)}%</b></div>
                <div><p className="text-xs text-muted-foreground">PREMIUM</p><b>${Number(evidence.risk.premium).toLocaleString()}</b></div>
                <div><p className="text-xs text-muted-foreground">REVIEW STATUS</p><b>{evidence.application.review_status}</b></div>
              </div>
              <p className="mt-4 text-sm text-muted-foreground">Model: {evidence.risk.model_version} · Prediction timestamp: {evidence.risk.prediction_timestamp}</p>
              <p className="mt-2 text-sm">Human review required: <b>{evidence.human_review_required ? "Yes" : "No"}</b></p>
              {evidence.application.decision_reason && <p className="mt-2 text-sm">Decision reason: {evidence.application.decision_reason}</p>}
              {evidence.risk.warnings.map((warning) => <p key={warning} className="mt-2 text-sm text-amber-300">{warning}</p>)}
            </EvidenceCard>

            <div className="grid gap-6 lg:grid-cols-2">
              <EvidenceCard title="Risk factors">
                {evidence.risk.important_features.length ? <ul className="space-y-2">
                  {evidence.risk.important_features.map((item) => <li key={item.feature} className="flex justify-between gap-3 text-sm">
                    <span>{item.feature} <span className="text-muted-foreground">({item.evidence_type})</span></span>
                    <b>{(item.importance * 100).toFixed(1)}%</b>
                  </li>)}
                </ul> : <p className="text-sm text-muted-foreground">Model feature-importance evidence is unavailable.</p>}
                {evidence.risk.rule_factors.length > 0 && <div className="mt-4 border-t border-white/10 pt-4">
                  <h3 className="font-medium">Rule-based adjustments</h3>
                  {evidence.risk.rule_factors.map((item) => <p key={item.feature} className="mt-2 text-sm">{item.feature}: +{(item.adjustment * 100).toFixed(1)} percentage points</p>)}
                </div>}
              </EvidenceCard>

              <EvidenceCard title="Statistical evidence">
                <p className="text-sm">Comparison sample: {evidence.statistics.sample_size} applications</p>
                <p className="mt-2 text-sm">Mean final risk: {evidence.statistics.risk_score_summary.mean === null ? "Unavailable" : `${(evidence.statistics.risk_score_summary.mean * 100).toFixed(1)}%`}</p>
                <div className="mt-4 grid grid-cols-3 gap-2 text-sm">
                  {Object.entries(evidence.statistics.risk_groups).map(([category, group]) => <div key={category} className="rounded-xl bg-white/5 p-3">
                    <b className="capitalize">{category}</b><p>{group.count} cases</p>
                    <p>Avg. risk: {group.mean_risk === null ? "—" : `${(group.mean_risk * 100).toFixed(1)}%`}</p>
                  </div>)}
                </div>
                {evidence.statistics.subject_comparison && <p className="mt-4 text-sm">This case is in the {evidence.statistics.subject_comparison.risk_category} cohort ({evidence.statistics.subject_comparison.cohort_size} cases).</p>}
                {evidence.statistics.outliers.map((item) => <p key={item.feature} className="mt-2 text-sm">Outlier signal: {item.feature}={item.value} ({item.method})</p>)}
                {evidence.statistics.limitations.map((item) => <p key={item} className="mt-3 text-xs text-amber-300">{item}</p>)}
              </EvidenceCard>

              <EvidenceCard title="Relationship intelligence">
                <p className="text-sm">Source: {evidence.graph_evidence.source} · Neo4j {evidence.graph_evidence.neo4j_configured ? "configured" : "not configured"}</p>
                <p className="mt-2 text-sm">{evidence.graph_evidence.nodes.length} related entities · {evidence.graph_evidence.edges.length} relationships · {evidence.claims.length} related claims</p>
                {evidence.graph_evidence.nodes.length ? <ul className="mt-3 space-y-2 text-sm">
                  {evidence.graph_evidence.nodes.map((node) => <li key={node.id}><b className="capitalize">{node.type}</b> · {node.id}</li>)}
                </ul> : <p className="mt-3 text-sm text-muted-foreground">No related graph entities are recorded for this application.</p>}
              </EvidenceCard>

              <EvidenceCard title="Retrieved policy evidence">
                {evidence.policy_evidence.length ? <div className="space-y-3">
                  {evidence.policy_evidence.map((item, index) => <article key={`${item.source}-${item.section}-${index}`} className="rounded-xl border border-white/10 p-3">
                    <p className="text-xs text-muted-foreground">{item.source} · section {item.section ?? "unknown"} · {item.retrieval}</p>
                    <p className="mt-2 whitespace-pre-wrap text-sm">{item.text}</p>
                  </article>)}
                </div> : <p className="text-sm text-muted-foreground">No indexed or matching policy-document evidence is available for this case.</p>}
              </EvidenceCard>
            </div>

            <EvidenceCard title="AI underwriter assistant">
              <p className="text-sm text-muted-foreground">Evidence-based decision support only. The human underwriter makes every final decision.</p>
              <label htmlFor="assistant-question" className="mt-4 block text-sm font-medium">Investigation question</label>
              <input id="assistant-question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={500} className="mt-2 w-full rounded-xl border border-white/10 bg-background px-3 py-2 text-sm" />
              <Button className="mt-3" onClick={() => void requestAssistant()} disabled={assistantLoading || !question.trim()}>
                {assistantLoading ? "Analyzing evidence…" : "Generate evidence summary"}
              </Button>
              {assistantError && <p role="alert" className="mt-3 text-sm text-destructive">{assistantError}</p>}
              {evidence.ai_explanation.summary && <p className="mt-4 whitespace-pre-wrap rounded-xl bg-white/5 p-4 text-sm">{evidence.ai_explanation.summary}</p>}
              {evidence.ai_explanation.warning && <p role="status" className="mt-3 text-sm text-amber-300">{evidence.ai_explanation.warning}</p>}
            </EvidenceCard>
          </div> : null}
    </DashboardLayout>
  )
}

export default function CaseIntelligencePage() {
  return (
    <RoleGuard allowedRoles={["underwriter", "claims_officer", "admin"]}>
      <Suspense fallback={<div className="p-8">Loading case…</div>}>
        <CaseIntelligence />
      </Suspense>
    </RoleGuard>
  )
}
