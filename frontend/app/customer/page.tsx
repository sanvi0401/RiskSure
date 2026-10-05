"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { apiFetch, API_ENDPOINTS } from "@/lib/api"

interface CustomerApplication {
  id: number
  name: string
  final_risk: number
  decision: string
  decision_reason: string | null
  premium: number
  review_status: string
  created_at: string | null
}

interface CustomerPortal {
  profile: { id: number; full_name: string; phone: string | null; city: string | null; state: string | null }
  policies: { id: number; policy_number: string; status: string; premium_amount: number }[]
  claims: { id: number; claim_number: string; status: string }[]
  applications: CustomerApplication[]
}

function CustomerDashboard() {
  const [data, setData] = useState<CustomerPortal | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    apiFetch(API_ENDPOINTS.customerPortal)
      .then(async (response) => {
        const body: unknown = await response.json().catch(() => null)
        if (!response.ok) throw new Error((body as { error?: string } | null)?.error || `Unable to load customer portal (${response.status})`)
        setData(body as CustomerPortal)
      })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Unable to load customer portal"))
      .finally(() => setLoading(false))
  }, [])

  const counts = useMemo(() => {
    const applications = data?.applications ?? []
    return {
      total: applications.length,
      pending: applications.filter((item) => item.review_status === "pending" || item.review_status === "draft").length,
      inReview: applications.filter((item) => item.review_status === "in_review" || item.review_status === "manual_review").length,
      approved: applications.filter((item) => item.decision === "Approved" || item.decision === "Approved with Conditions").length,
      rejected: applications.filter((item) => item.decision === "Rejected").length,
    }
  }, [data])

  return (
    <DashboardLayout title="Customer Portal" subtitle="Your applications, policies, claims, and underwriting status">
      {loading ? <div role="status" className="glass-panel rounded-[2rem] p-10 text-center">Loading your insurance workspace…</div>
        : error ? <div role="alert" className="glass-panel rounded-[2rem] p-6 text-destructive">{error}</div>
          : data ? <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div><h2 className="text-2xl font-semibold">Welcome, {data.profile.full_name}</h2><p className="text-sm text-muted-foreground">{[data.profile.city, data.profile.state].filter(Boolean).join(", ") || "Customer profile"}</p></div>
              <Link href="/new-application"><Button>Start an application</Button></Link>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {[
                ["Applications", counts.total],
                ["Pending", counts.pending],
                ["Under review", counts.inReview],
                ["Approved", counts.approved],
                ["Rejected", counts.rejected],
              ].map(([label, value]) => <div key={label} className="glass-panel rounded-2xl p-5">
                <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p><b className="mt-2 block text-3xl">{value}</b>
              </div>)}
            </div>

            <section className="glass-panel rounded-[2rem] p-6">
              <h2 className="text-xl font-semibold">My applications</h2>
              {data.applications.length ? <div className="mt-4 space-y-3">
                {data.applications.slice().sort((left, right) => (right.created_at ?? "").localeCompare(left.created_at ?? "")).map((application) => (
                  <Link key={application.id} href={`/applications/${application.id}`} className="block rounded-2xl border border-white/10 p-4 transition-colors hover:bg-white/5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <b>Application #{application.id}</b>
                      <span className="rounded-full border border-white/10 px-3 py-1 text-xs">{application.review_status.replaceAll("_", " ")}</span>
                    </div>
                    <div className="mt-3 grid gap-2 text-sm text-muted-foreground sm:grid-cols-3">
                      <span>Risk: {(application.final_risk * 100).toFixed(1)}%</span>
                      <span>Decision: {application.decision}</span>
                      <span>Premium: ${Number(application.premium).toLocaleString()}</span>
                    </div>
                    {application.decision_reason && <p className="mt-2 text-sm">Decision explanation: {application.decision_reason}</p>}
                  </Link>
                ))}
              </div> : <p className="mt-4 text-sm text-muted-foreground">You haven’t submitted an application yet.</p>}
            </section>

            <div className="grid gap-6 md:grid-cols-2">
              <section className="glass-panel rounded-[2rem] p-6">
                <h2 className="text-xl font-semibold">Policies</h2>
                <p className="mt-2 text-sm text-muted-foreground">{data.policies.length} policies</p>
                {data.policies.map((policy) => <p key={policy.id} className="mt-3 text-sm">{policy.policy_number} · {policy.status} · ${Number(policy.premium_amount).toLocaleString()}</p>)}
                {!data.policies.length && <p className="mt-3 text-sm text-muted-foreground">No policies available.</p>}
              </section>
              <section className="glass-panel rounded-[2rem] p-6">
                <h2 className="text-xl font-semibold">Claims</h2>
                <p className="mt-2 text-sm text-muted-foreground">{data.claims.length} claims</p>
                {data.claims.map((claim) => <p key={claim.id} className="mt-3 text-sm">{claim.claim_number} · {claim.status}</p>)}
                {!data.claims.length && <p className="mt-3 text-sm text-muted-foreground">No claims available.</p>}
              </section>
            </div>
          </div> : null}
    </DashboardLayout>
  )
}

export default function CustomerPage() {
  return <RoleGuard allowedRoles={["customer"]}><CustomerDashboard /></RoleGuard>
}
