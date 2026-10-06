"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { ArrowRight, CheckCircle2, FileText, Layers, Loader2, Network, RefreshCw, UserPlus } from "lucide-react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel } from "@/components/ui/alert-dialog"
import { useAuth } from "@/context/auth-context"
import { apiJson, API_ENDPOINTS } from "@/lib/api"
import { filterUnderwritingQueue, type UnderwritingApplication, type QueueView, type QueueSort } from "@/lib/underwriting"

const views = [{ value: "open", label: "Needs review" }, { value: "mine", label: "My cases" }, { value: "unassigned", label: "Unassigned" }, { value: "completed", label: "Completed" }] as const

function UnderwriterDashboard() {
  const { user } = useAuth()
  const [applications, setApplications] = useState<UnderwritingApplication[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [view, setView] = useState<QueueView>("open")
  const [sort, setSort] = useState<QueueSort>("oldest")
  const [search, setSearch] = useState("")
  const [queryReady, setQueryReady] = useState(false)
  const [decision, setDecision] = useState("")
  const [reason, setReason] = useState("")
  const [confirming, setConfirming] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const selected = applications.find(application => application.id === selectedId) ?? null
  const completed = selected?.review_status === "completed"
  const assigned = selected?.assigned_underwriter_id === user?.id
  const canDecide = !!selected && !completed && (assigned || user?.role === "admin")
  const visible = filterUnderwritingQueue(applications, view, user?.id, search, sort)

  const loadApplications = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError("")
    try {
      const data = await apiJson<UnderwritingApplication[]>(API_ENDPOINTS.underwritingQueue, { signal })
      if (!Array.isArray(data) || !data.every(item => typeof item.id === "number" && typeof item.name === "string" && typeof item.review_status === "string")) throw new Error("Invalid underwriting queue response")
      if (!signal?.aborted) setApplications(data)
    } catch (caught) {
      if (!signal?.aborted) setError(caught instanceof Error ? caught.message : "Unable to load the queue")
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const id = Number(params.get("case"))
    if (Number.isSafeInteger(id) && id > 0) setSelectedId(id)
    if (views.some(item => item.value === params.get("view"))) setView(params.get("view") as QueueView)
    setQueryReady(true)
    const controller = new AbortController()
    void loadApplications(controller.signal)
    return () => controller.abort()
  }, [loadApplications])

  useEffect(() => {
    if (!queryReady || loading) return
    const params = new URLSearchParams(window.location.search)
    const currentView = selected?.review_status === "completed" ? "completed" : view
    if (selected?.review_status === "completed" && view !== "completed") setView("completed")
    params.set("view", currentView)
    if (selectedId) params.set("case", String(selectedId)); else params.delete("case")
    window.history.replaceState(null, "", `${window.location.pathname}?${params}`)
  }, [selectedId, selected?.review_status, view, queryReady, loading])

  const choose = (id: number | null) => {
    setSelectedId(id); setDecision(""); setReason(""); setMessage(""); setError(""); setConfirming(false)
  }

  const assignToMe = async () => {
    if (!selected || completed || saving) return
    setSaving(true); setError(""); setMessage("")
    try {
      await apiJson(API_ENDPOINTS.underwritingAssign(selected.id), { method: "PUT", body: JSON.stringify({}) })
      setMessage("Application assigned to you.")
      await loadApplications()
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to assign application") }
    finally { setSaving(false) }
  }

  const recordDecision = async () => {
    if (!selected || !canDecide || !decision || !reason.trim() || saving) return
    setSaving(true); setError(""); setMessage("")
    try {
      await apiJson(API_ENDPOINTS.underwritingDecision(selected.id), { method: "PUT", body: JSON.stringify({ decision, reason: reason.trim() }) })
      setConfirming(false)
      setMessage(`Decision recorded for case #${selected.id}: ${decision}.`)
      setDecision(""); setReason("")
      await loadApplications()
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to record decision") }
    finally { setSaving(false) }
  }

  return <DashboardLayout title="Underwriting Centre" subtitle="Application queue and human review">
    {error && <p role="alert" className="mb-4 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
    {message && <p role="status" className="mb-4 text-sm text-primary">{message}</p>}
    <Tabs value={view} onValueChange={value => { setView(value as QueueView); choose(null) }}>
      <TabsList aria-label="Queue views" className="grid h-auto w-full grid-cols-2 gap-1 sm:grid-cols-4">
        {views.map(item => <TabsTrigger key={item.value} value={item.value} disabled={saving} className="min-h-10 gap-2 text-xs sm:text-sm">{item.label}<span className="text-xs">{filterUnderwritingQueue(applications, item.value, user?.id).length}</span></TabsTrigger>)}
      </TabsList>
    </Tabs>
    <div className="mt-5 grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section className="min-w-0">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Application queue</h2><Button variant="ghost" size="icon" title="Refresh queue" aria-label="Refresh queue" disabled={loading || saving} onClick={() => void loadApplications()}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></Button></div>
        <div className="my-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_180px]"><Input aria-label="Search applications" placeholder="Search name or case number" value={search} onChange={event => setSearch(event.target.value)} disabled={saving} /><select aria-label="Sort applications" value={sort} onChange={event => setSort(event.target.value as QueueSort)} className="h-9 rounded-md border border-input bg-background px-3 text-sm"><option value="oldest">Oldest first</option><option value="newest">Newest first</option><option value="risk">Highest risk first</option></select></div>
        {loading ? <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading applications...</p> :
          <div className="space-y-3">{visible.map(application => <button key={application.id} type="button" aria-pressed={selectedId === application.id} disabled={saving} onClick={() => choose(application.id)} className={`w-full rounded-lg border p-4 text-left disabled:opacity-60 ${selectedId === application.id ? "border-primary bg-primary/10" : "border-border hover:bg-muted/30"}`}>
            <div className="flex flex-wrap justify-between gap-2"><b className="break-words">{application.name}</b><span className="text-sm">{application.final_risk === null ? "Not scored" : `${Math.round(application.final_risk * 100)}% risk`}</span></div>
            <p className="mt-2 text-xs text-muted-foreground">Case #{application.id} | {application.review_status.replaceAll("_", " ")} | {application.assigned_underwriter_id === null ? "Unassigned" : application.assigned_underwriter_id === user?.id ? "Assigned to you" : "Assigned"}</p>
            {application.review_status === "completed" && <p className="mt-2 text-sm">{application.decision}</p>}
          </button>)}{!visible.length && !error && <p className="py-6 text-sm text-muted-foreground">{search ? "No applications match your search." : "No applications in this view."}</p>}</div>}
      </section>
      <aside className="min-w-0 border-t border-border pt-5 xl:border-l xl:border-t-0 xl:pl-6 xl:pt-0">
        {selected ? <>
          <p className="text-xs text-muted-foreground">CASE #{selected.id} | {selected.review_status.replaceAll("_", " ")}</p><h2 className="mt-2 break-words text-xl font-semibold">{selected.name}</h2>
          <dl className="mt-5 grid grid-cols-2 gap-4 text-sm"><div><dt className="text-muted-foreground">Final risk</dt><dd className="mt-1 font-semibold">{selected.final_risk === null ? "Not scored" : `${(selected.final_risk * 100).toFixed(1)}%`}</dd></div><div><dt className="text-muted-foreground">Premium</dt><dd className="mt-1 font-semibold">${Number(selected.premium || 0).toLocaleString()}</dd></div><div><dt className="text-muted-foreground">BMI</dt><dd>{selected.bmi ?? "Not recorded"}</dd></div><div><dt className="text-muted-foreground">Smoker</dt><dd>{selected.smoker ?? "Not recorded"}</dd></div></dl>
          <h3 className="mt-6 text-sm font-semibold">Case investigation</h3><div className="mt-3 grid gap-2">
            <Button asChild variant="outline"><Link href={`/underwriter/applications/${selected.id}`}><FileText className="h-4 w-4" />Application details</Link></Button>
            <Button asChild variant="outline"><Link href={`/case-intelligence?id=${selected.id}`}><Layers className="h-4 w-4" />Case evidence</Link></Button>
            <Button asChild variant="outline"><Link href={`/relationship-graph?application_id=${selected.id}`}><Network className="h-4 w-4" />Relationship graph</Link></Button>
          </div>
          {completed ? <div className="mt-6 border-t border-border pt-5"><h3 className="flex items-center gap-2 text-sm font-semibold"><CheckCircle2 className="h-4 w-4 text-primary" />Completed decision</h3><p className="mt-3 font-medium">{selected.decision}</p><p className="mt-2 whitespace-pre-wrap break-words text-sm text-muted-foreground">{selected.decision_reason || "No reason recorded."}</p><Button className="mt-4 w-full" variant="outline" onClick={() => { setView("open"); setSearch(""); choose(filterUnderwritingQueue(applications, "open", user?.id, "", sort)[0]?.id ?? null) }}>Next open case<ArrowRight className="h-4 w-4" /></Button></div> :
            <div className="mt-6 border-t border-border pt-5"><h3 className="text-sm font-semibold">Human decision</h3>
              {assigned ? <p className="mt-3 text-sm text-primary">Assigned to you</p> : <Button className="mt-3 w-full" variant="outline" onClick={() => void assignToMe()} disabled={saving}><UserPlus className="h-4 w-4" />Assign to me</Button>}
              <Label htmlFor="underwriting-decision" className="mt-4 block">Decision</Label><select id="underwriting-decision" value={decision} disabled={saving || !canDecide} onChange={event => setDecision(event.target.value)} className="mt-2 h-10 w-full rounded-md border border-input bg-background px-3 text-sm"><option value="">Select decision</option><option>Approved</option><option>Approved with Conditions</option><option>Manual Review</option><option>Rejected</option></select>
              <Label htmlFor="underwriting-reason" className="mt-4 block">Decision reason</Label><textarea id="underwriting-reason" value={reason} onChange={event => setReason(event.target.value)} maxLength={2000} disabled={saving || !canDecide} className="mt-2 min-h-24 w-full rounded-md border border-input bg-background p-3 text-sm" />
              <Button className="mt-3 w-full" disabled={saving || !canDecide || !decision || !reason.trim()} onClick={() => setConfirming(true)}>Review decision<ArrowRight className="h-4 w-4" /></Button>
            </div>}
        </> : <p className="text-sm text-muted-foreground">Select an application to review.</p>}
      </aside>
    </div>
    <AlertDialog open={confirming} onOpenChange={value => { if (!saving) setConfirming(value) }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>Confirm underwriting decision</AlertDialogTitle><AlertDialogDescription>Case #{selected?.id}: {selected?.name}</AlertDialogDescription></AlertDialogHeader><p className="font-semibold">{decision}</p><p className="max-h-48 overflow-auto whitespace-pre-wrap break-words text-sm text-muted-foreground">{reason}</p>{error && <p role="alert" className="text-sm text-destructive">{error}</p>}<AlertDialogFooter><AlertDialogCancel disabled={saving}>Back to review</AlertDialogCancel><Button disabled={saving} onClick={() => void recordDecision()}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}{saving ? "Saving..." : "Record decision"}</Button></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </DashboardLayout>
}

export default function UnderwriterDashboardPage() {
  return <RoleGuard allowedRoles={["underwriter", "admin"]}><UnderwriterDashboard /></RoleGuard>
}
