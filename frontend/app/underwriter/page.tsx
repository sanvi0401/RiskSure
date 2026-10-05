"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { apiFetch, API_ENDPOINTS } from "@/lib/api"

interface UnderwritingApplication {
  id: number
  name: string
  age: number | null
  bmi: number | null
  smoker: string | null
  final_risk: number | null
  decision: string | null
  premium: number | null
  review_status: string
  assigned_underwriter_id: number | null
}

function isUnderwritingApplication(value: unknown): value is UnderwritingApplication {
  if (typeof value !== "object" || value === null) return false
  const application = value as Record<string, unknown>
  return typeof application.id === "number"
    && typeof application.name === "string"
    && (typeof application.age === "number" || application.age === null)
    && (typeof application.bmi === "number" || application.bmi === null)
    && (typeof application.smoker === "string" || application.smoker === null)
    && (typeof application.final_risk === "number" || application.final_risk === null)
    && (typeof application.decision === "string" || application.decision === null)
    && (typeof application.premium === "number" || application.premium === null)
    && typeof application.review_status === "string"
    && (typeof application.assigned_underwriter_id === "number" || application.assigned_underwriter_id === null)
}

async function responseError(response: Response, fallback: string): Promise<Error> {
  const body = await response.json().catch(() => null)
  return new Error(body?.error || `${fallback} (${response.status})`)
}

function UnderwriterDashboard() {
  const [applications, setApplications] = useState<UnderwritingApplication[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [decision, setDecision] = useState("")
  const [reason, setReason] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const selected = applications.find((application) => application.id === selectedId) ?? null

  const loadApplications = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const response = await apiFetch(API_ENDPOINTS.underwritingQueue)
      if (!response.ok) throw await responseError(response, "Unable to load underwriting queue")
      const data: unknown = await response.json()
      if (!Array.isArray(data) || !data.every(isUnderwritingApplication)) {
        throw new Error("The underwriting queue response is invalid")
      }
      setApplications(data)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load underwriting queue")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadApplications()
  }, [loadApplications])

  const assignToMe = async () => {
    if (!selected) return
    setSaving(true)
    setError("")
    setMessage("")
    try {
      const response = await apiFetch(API_ENDPOINTS.underwritingAssign(selected.id), {
        method: "PUT",
        body: JSON.stringify({}),
      })
      if (!response.ok) throw await responseError(response, "Unable to assign application")
      setMessage("Application assigned to you.")
      await loadApplications()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unable to assign application")
    } finally {
      setSaving(false)
    }
  }

  const recordDecision = async () => {
    if (!selected || !decision || !reason.trim()) return
    setSaving(true)
    setError("")
    setMessage("")
    try {
      const response = await apiFetch(API_ENDPOINTS.underwritingDecision(selected.id), {
        method: "PUT",
        body: JSON.stringify({ decision, reason: reason.trim() }),
      })
      if (!response.ok) throw await responseError(response, "Unable to record decision")
      setMessage("Decision recorded.")
      setSelectedId(null)
      setDecision("")
      setReason("")
      await loadApplications()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unable to record decision")
    } finally {
      setSaving(false)
    }
  }

  return (
    <DashboardLayout title="Underwriting Centre" subtitle="Review applications and record human decisions">
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <section className="glass-panel rounded-[2rem] p-6">
          <div className="mb-5 flex items-center justify-between gap-4">
            <h2 className="text-2xl font-semibold">Application queue</h2>
            <Button variant="outline" onClick={() => void loadApplications()} disabled={loading}>
              Refresh
            </Button>
          </div>
          <div className="mb-5 grid grid-cols-3 gap-3 text-sm">
            <div className="rounded-xl bg-white/5 p-3">Total <b>{applications.length}</b></div>
            <div className="rounded-xl bg-white/5 p-3">In review <b>{applications.filter((item) => item.review_status === "in_review").length}</b></div>
            <div className="rounded-xl bg-white/5 p-3">Manual <b>{applications.filter((item) => item.review_status === "manual_review").length}</b></div>
          </div>
          {loading ? <p className="text-sm text-muted-foreground">Loading applications…</p> : applications.length === 0 ? (
            <p className="text-sm text-muted-foreground">No applications are currently awaiting review.</p>
          ) : (
            <div className="space-y-3">
              {applications.map((application) => (
                <button
                  key={application.id}
                  type="button"
                  aria-pressed={selectedId === application.id}
                  onClick={() => {
                    setSelectedId(application.id)
                    setDecision("")
                    setReason("")
                    setMessage("")
                  }}
                  className={`w-full rounded-2xl border p-4 text-left ${selectedId === application.id ? "border-primary bg-primary/10" : "border-white/10"}`}
                >
                  <div className="flex justify-between gap-3">
                    <b>{application.name}</b>
                    <span>{Math.round((application.final_risk ?? 0) * 100)}% risk</span>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Case #{application.id} · {application.review_status} · ${Number(application.premium || 0).toLocaleString()}
                  </div>
                </button>
              ))}
            </div>
          )}
        </section>

        <aside className="glass-panel rounded-[2rem] p-6">
          {selected ? (
            <>
              <p className="text-xs text-muted-foreground">CASE #{selected.id}</p>
              <h2 className="mt-2 text-2xl font-semibold">{selected.name}</h2>
              <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl bg-white/5 p-3">Risk<br /><b>{((selected.final_risk ?? 0) * 100).toFixed(1)}%</b></div>
                <div className="rounded-xl bg-white/5 p-3">Premium<br /><b>${Number(selected.premium || 0).toLocaleString()}</b></div>
                <div className="rounded-xl bg-white/5 p-3">BMI<br /><b>{selected.bmi ?? "Not recorded"}</b></div>
                <div className="rounded-xl bg-white/5 p-3">Smoker<br /><b>{selected.smoker ?? "Not recorded"}</b></div>
              </div>
              <Link className="mt-4 block text-center text-sm text-primary hover:underline" href={`/case-intelligence?id=${selected.id}`}>
                Open evidence review
              </Link>
              <Link className="mt-2 block text-center text-sm text-primary hover:underline" href={`/relationship-graph?application_id=${selected.id}`}>
                Open application relationship graph
              </Link>
              <Button className="mt-5 w-full" variant="outline" onClick={() => void assignToMe()} disabled={saving}>
                Assign to me
              </Button>
              <label className="mt-4 block text-sm font-medium" htmlFor="underwriting-decision">Decision</label>
              <select
                id="underwriting-decision"
                value={decision}
                onChange={(event) => setDecision(event.target.value)}
                className="mt-2 h-11 w-full rounded-xl border bg-background px-3"
              >
                <option value="">Select decision</option>
                <option>Approved</option>
                <option>Approved with Conditions</option>
                <option>Manual Review</option>
                <option>Rejected</option>
              </select>
              <label className="mt-3 block text-sm font-medium" htmlFor="underwriting-reason">Decision reason</label>
              <Input id="underwriting-reason" className="mt-2" value={reason} onChange={(event) => setReason(event.target.value)} />
              <Button className="mt-3 w-full" disabled={saving || !decision || !reason.trim()} onClick={() => void recordDecision()}>
                {saving ? "Saving…" : "Record decision"}
              </Button>
            </>
          ) : (
            <p className="text-muted-foreground">Select an application to review.</p>
          )}
          {error && <p role="alert" className="mt-4 rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
          {message && <p role="status" className="mt-4 rounded-xl bg-primary/10 p-3 text-sm">{message}</p>}
        </aside>
      </div>
    </DashboardLayout>
  )
}

export default function UnderwriterDashboardPage() {
  return (
    <RoleGuard allowedRoles={["underwriter", "admin"]}>
      <UnderwriterDashboard />
    </RoleGuard>
  )
}
