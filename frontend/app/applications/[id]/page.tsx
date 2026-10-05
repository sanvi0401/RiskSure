"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { apiJson, API_ENDPOINTS } from "@/lib/api"

interface ApplicationDetails {
  id: number
  name: string
  age: number | null
  sex: string | null
  bmi: number | null
  children: number | null
  smoker: string | null
  region: string | null
  risk_score: number
  final_risk: number
  decision: string
  decision_reason: string | null
  premium: number
  review_status: string
  created_at: string | null
  reviewed_at: string | null
}

function ApplicationDetailsView() {
  const params = useParams<{ id: string }>()
  const parsedId = Number(params.id)
  const [application, setApplication] = useState<ApplicationDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!Number.isSafeInteger(parsedId) || parsedId <= 0) {
      setError("Invalid application ID.")
      setLoading(false)
      return
    }
    apiJson<ApplicationDetails>(API_ENDPOINTS.application(parsedId))
      .then(setApplication)
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Unable to load application"))
      .finally(() => setLoading(false))
  }, [parsedId])

  return (
    <DashboardLayout title="Application Details" subtitle="Application status and underwriting decision">
      {loading ? <div role="status" className="glass-panel rounded-[2rem] p-8">Loading application…</div>
        : error ? <div role="alert" className="glass-panel rounded-[2rem] p-6 text-destructive">{error}</div>
          : application ? <div className="space-y-6">
            <section className="glass-panel rounded-[2rem] p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div><p className="text-xs text-muted-foreground">APPLICATION #{application.id}</p><h2 className="mt-2 text-2xl font-semibold">{application.name}</h2></div>
                <span className="rounded-full border border-white/10 px-3 py-1 text-sm">{application.review_status.replaceAll("_", " ")}</span>
              </div>
              <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div><p className="text-xs text-muted-foreground">RISK SCORE</p><b>{(application.risk_score * 100).toFixed(1)}%</b></div>
                <div><p className="text-xs text-muted-foreground">FINAL RISK</p><b>{(application.final_risk * 100).toFixed(1)}%</b></div>
                <div><p className="text-xs text-muted-foreground">PREMIUM</p><b>${Number(application.premium).toLocaleString()}</b></div>
                <div><p className="text-xs text-muted-foreground">DECISION</p><b>{application.decision}</b></div>
              </div>
              <p className="mt-5 text-sm">{application.decision_reason || "Your application is awaiting an underwriter decision."}</p>
              <p className="mt-2 text-xs text-muted-foreground">Submitted: {application.created_at ? new Date(application.created_at).toLocaleString() : "Not recorded"}{application.reviewed_at ? ` · Reviewed: ${new Date(application.reviewed_at).toLocaleString()}` : ""}</p>
            </section>
            <section className="glass-panel rounded-[2rem] p-6">
              <h2 className="text-xl font-semibold">Applicant information</h2>
              <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
                <p>Age: {application.age ?? "Not recorded"}</p><p>Sex: {application.sex ?? "Not recorded"}</p>
                <p>BMI: {application.bmi ?? "Not recorded"}</p><p>Children: {application.children ?? "Not recorded"}</p>
                <p>Smoker: {application.smoker ?? "Not recorded"}</p><p>Region: {application.region ?? "Not recorded"}</p>
              </div>
            </section>
            <div className="flex flex-wrap gap-3">
              <Link href="/dashboard"><Button variant="outline">Back to dashboard</Button></Link>
            </div>
          </div> : null}
    </DashboardLayout>
  )
}

export default function ApplicationDetailsPage() {
  return <RoleGuard allowedRoles={["customer", "underwriter", "admin"]}><ApplicationDetailsView /></RoleGuard>
}
