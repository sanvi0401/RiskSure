"use client"

import { useEffect, useState } from "react"
import { FileText, Loader2, MessageSquare, Save } from "lucide-react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuth } from "@/context/auth-context"
import { apiFetch, API_ENDPOINTS } from "@/lib/api"

type Policy = {
  id: number; policy_number: string; policy_type: string; status: string
  coverage_limit: number; premium_amount: number; terms_document: string | null
}
type Answer = {
  answer: string; sources: { section?: number; text: string }[]
  retrieval: string; ai_available: boolean
}
const money = (value: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value || 0)

export default function Page() {
  return <RoleGuard allowedRoles={["customer", "underwriter", "claims_officer", "admin"]}><PolicyCentre /></RoleGuard>
}

function PolicyCentre() {
  const { hasRole } = useAuth()
  const canEdit = hasRole(["underwriter", "claims_officer", "admin"])
  const [policies, setPolicies] = useState<Policy[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = policies.find(policy => policy.id === selectedId)
  const [question, setQuestion] = useState("")
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [document, setDocument] = useState("")
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<"ask" | "save" | null>(null)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        const response = await apiFetch(API_ENDPOINTS.policies, { signal: controller.signal })
        const data = await response.json().catch(() => null)
        if (!response.ok) throw new Error(data?.error || "Unable to load policies")
        if (!Array.isArray(data)) throw new Error("Invalid policy response")
        if (!controller.signal.aborted) setPolicies(data)
      } catch (caught) {
        if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Unable to load policies")
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [])

  const choose = (policy: Policy) => {
    setSelectedId(policy.id)
    setQuestion("")
    setAnswer(null)
    setDocument(policy.terms_document || "")
    setError("")
    setMessage("")
  }

  const ask = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!selected || !question.trim() || busy) return
    setBusy("ask")
    setError("")
    setAnswer(null)
    setMessage("")
    try {
      const response = await apiFetch(API_ENDPOINTS.policyIntelligence(selected.id), {
        method: "POST", body: JSON.stringify({ question: question.trim() }), timeoutMs: 90_000,
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(data?.error || "Unable to answer the policy question")
      if (!data?.answer || !Array.isArray(data.sources)) throw new Error("Invalid policy intelligence response")
      setAnswer(data)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to answer the policy question")
    } finally {
      setBusy(null)
    }
  }

  const save = async () => {
    if (!selected || !canEdit || !document.trim() || busy) return
    setBusy("save")
    setError("")
    setMessage("")
    try {
      const response = await apiFetch(API_ENDPOINTS.policyDocument(selected.id), {
        method: "PUT", body: JSON.stringify({ document_text: document.trim() }),
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(data?.error || "Unable to save the policy document")
      if (!data?.policy) throw new Error("Invalid policy document response")
      setPolicies(current => current.map(policy => policy.id === selected.id ? data.policy : policy))
      setDocument(data.policy.terms_document || "")
      setAnswer(null)
      setMessage("Policy document saved.")
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save the policy document")
    } finally {
      setBusy(null)
    }
  }

  return <DashboardLayout title="Policy Centre" subtitle="Policy documents and clause intelligence">
    {error && <p role="alert" className="mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
    <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,420px)]">
      <section className="min-w-0">
        <h2 className="text-xl font-semibold">Policies</h2>
        {loading ? <p role="status" className="mt-5 flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading policies...</p> :
          <div className="mt-5 space-y-3">
            {policies.map(policy => <button key={policy.id} onClick={() => choose(policy)} disabled={!!busy}
              aria-pressed={selectedId === policy.id} className={`w-full rounded-lg border p-4 text-left disabled:opacity-60 ${selectedId === policy.id ? "border-primary bg-primary/10" : "border-border hover:bg-muted/30"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2"><b className="break-all">{policy.policy_number}</b><span className="text-sm capitalize">{policy.status}</span></div>
              <p className="mt-2 text-sm text-muted-foreground">{policy.policy_type} | Coverage {money(policy.coverage_limit)}</p>
              <p className="mt-1 text-sm text-muted-foreground">Premium {money(policy.premium_amount)}</p>
            </button>)}
            {!policies.length && !error && <p className="text-sm text-muted-foreground">No policies available.</p>}
          </div>}
      </section>
      <aside className="min-w-0 border-t border-border pt-6 xl:border-l xl:border-t-0 xl:pl-6 xl:pt-0">
        {selected ? <>
          <h2 className="break-all text-xl font-semibold">{selected.policy_number}</h2>
          <h3 className="mt-5 flex items-center gap-2 text-sm font-semibold"><FileText className="h-4 w-4" />Policy document</h3>
          {selected.terms_document ? <p className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words text-sm text-muted-foreground">{selected.terms_document}</p> : <p className="mt-3 text-sm text-muted-foreground">No policy document available.</p>}
          <form onSubmit={ask} className="mt-6">
            <Label htmlFor="policy-question">Policy question</Label>
            <Input id="policy-question" className="mt-2" value={question} onChange={event => setQuestion(event.target.value)} maxLength={2000} disabled={!!busy} placeholder="Coverage, exclusions, eligibility..." />
            <Button type="submit" className="mt-3 w-full" disabled={!!busy || !question.trim() || !selected.terms_document}>
              {busy === "ask" ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageSquare className="h-4 w-4" />}{busy === "ask" ? "Retrieving answer..." : "Ask policy"}
            </Button>
          </form>
          {answer && <div className="mt-5 border-t border-border pt-4 text-sm" data-testid="policy-answer">
            <h3 className="font-semibold">{answer.ai_available ? "Policy answer" : "Retrieved policy excerpts"}</h3>
            <p className="mt-2 whitespace-pre-wrap break-words">{answer.answer}</p>
            {!answer.ai_available && <p className="mt-2 text-xs text-muted-foreground">AI unavailable. Showing the stored policy text.</p>}
            <p className="mt-3 text-xs text-muted-foreground">{answer.retrieval}</p>
            {answer.sources.map((source, index) => <p key={index} className="mt-2 break-words text-xs text-muted-foreground">Source {source.section ?? index + 1}: {source.text}</p>)}
          </div>}
          {canEdit && <div className="mt-6 border-t border-border pt-5">
            <Label htmlFor="policy-document">Edit policy document</Label>
            <textarea id="policy-document" value={document} onChange={event => setDocument(event.target.value)} maxLength={50000} disabled={!!busy} className="mt-2 min-h-40 w-full rounded-md border border-input bg-background p-3 text-sm" />
            <Button variant="outline" className="mt-3 w-full" onClick={save} disabled={!!busy || !document.trim() || document.trim() === selected.terms_document}>
              {busy === "save" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{busy === "save" ? "Saving..." : "Save document"}
            </Button>
          </div>}
          {message && <p role="status" className="mt-3 text-sm text-primary">{message}</p>}
        </> : <p className="text-sm text-muted-foreground">Select a policy.</p>}
      </aside>
    </div>
  </DashboardLayout>
}
