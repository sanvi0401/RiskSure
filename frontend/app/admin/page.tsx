"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { apiFetch, apiJson, API_ENDPOINTS } from "@/lib/api"

type UserRole = "customer" | "underwriter" | "claims_officer" | "provider" | "admin"
interface AdminUser { id: number; email: string; role: UserRole; created_at?: string | null }
interface AuditEntry {
  id: number
  user_id: number | null
  user_email: string | null
  role: string | null
  action: string
  entity_type: string
  entity_id: number | null
  details: Record<string, unknown> | null
  created_at: string | null
}
interface AdminOverview {
  users: number
  customers: number
  underwriters: number
  claims_officers: number
  providers_users: number
  providers: number
  policies: number
  applications: number
  pending_applications: number
  applications_under_review: number
  approved_applications: number
  rejected_applications: number
  high_risk_applications: number
  medium_risk_applications: number
  low_risk_applications: number
  risk_distribution: { low: number; medium: number; high: number }
  underwriting_workload: { user_id: number; email: string; assigned_applications: number }[]
  recent_activity: { id: number; user_id: number | null; action: string; entity_type: string; entity_id: number | null; created_at: string | null }[]
  claims: number
  billing_transactions: number
}

const roles: UserRole[] = ["customer", "underwriter", "claims_officer", "provider", "admin"]

function AdminDashboard() {
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [savingUser, setSavingUser] = useState<number | null>(null)
  const [userSearch, setUserSearch] = useState("")
  const [auditSearch, setAuditSearch] = useState("")
  const [auditRole, setAuditRole] = useState("")
  const [auditAction, setAuditAction] = useState("")
  const [auditEntity, setAuditEntity] = useState("")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [filtering, setFiltering] = useState(false)

  const loadOverviewAndUsers = useCallback(async () => {
    const [nextOverview, nextUsers] = await Promise.all([
      apiJson<AdminOverview>(API_ENDPOINTS.adminOverview),
      apiJson<AdminUser[]>(API_ENDPOINTS.adminUsers),
    ])
    setOverview(nextOverview)
    setUsers(nextUsers)
  }, [])

  const loadAudit = useCallback(async (query = "") => {
    const response = await apiJson<AuditEntry[]>(`${API_ENDPOINTS.adminAudit}${query ? `?${query}` : ""}`)
    setAudit(response)
  }, [])

  useEffect(() => {
    Promise.all([loadOverviewAndUsers(), loadAudit()])
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "Unable to load admin data"))
      .finally(() => setLoading(false))
  }, [loadAudit, loadOverviewAndUsers])

  const filteredUsers = useMemo(() => {
    const needle = userSearch.trim().toLowerCase()
    return needle ? users.filter((user) => user.email.toLowerCase().includes(needle) || String(user.id) === needle) : users
  }, [userSearch, users])

  const updateRole = async (userId: number, role: UserRole) => {
    setSavingUser(userId)
    setError("")
    try {
      const response = await apiFetch(API_ENDPOINTS.adminRole(userId), { method: "PUT", body: JSON.stringify({ role }) })
      const result = await response.json().catch(() => null)
      if (!response.ok) throw new Error(result?.error || `Unable to update role (${response.status})`)
      await loadOverviewAndUsers()
      await loadAudit()
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Unable to update user role")
    } finally {
      setSavingUser(null)
    }
  }

  const applyAuditFilters = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFiltering(true)
    setError("")
    const params = new URLSearchParams()
    params.set("limit", "200")
    if (auditSearch.trim()) params.set("search", auditSearch.trim())
    if (auditRole) params.set("role", auditRole)
    if (auditAction.trim()) params.set("action", auditAction.trim())
    if (auditEntity.trim()) params.set("entity_type", auditEntity.trim())
    if (startDate) params.set("start_date", startDate)
    if (endDate) params.set("end_date", endDate)
    try {
      await loadAudit(params.toString())
    } catch (filterError) {
      setError(filterError instanceof Error ? filterError.message : "Unable to filter audit log")
    } finally {
      setFiltering(false)
    }
  }

  const clearAuditFilters = async () => {
    setAuditSearch(""); setAuditRole(""); setAuditAction(""); setAuditEntity(""); setStartDate(""); setEndDate("")
    setFiltering(true); setError("")
    try { await loadAudit() }
    catch (filterError) { setError(filterError instanceof Error ? filterError.message : "Unable to load audit log") }
    finally { setFiltering(false) }
  }

  return (
    <DashboardLayout title="Admin Centre" subtitle="Organization metrics, role management, and security audit">
      {error && <div role="alert" className="mb-5 rounded-2xl border border-destructive/40 bg-destructive/10 p-4 text-sm">{error}</div>}
      {loading ? <div role="status" className="glass-panel rounded-[2rem] p-8 text-center">Loading administration data…</div> : overview && <>
        <section aria-label="Platform metrics" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            ["Users", overview.users], ["Customers", overview.customers], ["Applications", overview.applications],
            ["Pending review", overview.pending_applications], ["Under review", overview.applications_under_review],
            ["Approved", overview.approved_applications], ["Rejected", overview.rejected_applications],
            ["Claims", overview.claims], ["Policies", overview.policies], ["Provider accounts", overview.providers_users],
            ["Providers", overview.providers], ["Billing transactions", overview.billing_transactions],
          ].map(([label, value]) => <div key={label} className="glass-panel rounded-2xl p-5">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p><b className="mt-2 block text-3xl">{value}</b>
          </div>)}
        </section>

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <section className="glass-panel rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Risk distribution</h2>
            <div className="mt-4 grid grid-cols-3 gap-3">
              {(["low", "medium", "high"] as const).map((level) => <div key={level} className="rounded-2xl border border-white/10 p-4">
                <p className="text-xs uppercase text-muted-foreground">{level} risk</p><b className="mt-2 block text-2xl">{overview.risk_distribution[level]}</b>
              </div>)}
            </div>
          </section>
          <section className="glass-panel rounded-[2rem] p-6">
            <h2 className="text-xl font-semibold">Underwriting workload</h2>
            <div className="mt-4 space-y-2">
              {overview.underwriting_workload.length ? overview.underwriting_workload.map((item) => <div key={item.user_id} className="flex justify-between gap-4 rounded-xl border border-white/10 p-3 text-sm">
                <span>{item.email}</span><b>{item.assigned_applications} assigned</b>
              </div>) : <p className="text-sm text-muted-foreground">No underwriting assignments.</p>}
            </div>
          </section>
        </div>

        <section className="glass-panel mt-6 rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">Users and role management</h2>
          <input aria-label="Search users" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} placeholder="Search by email or user ID" className="mt-4 w-full rounded-xl border border-white/10 bg-background px-4 py-2 text-sm sm:max-w-sm" />
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {filteredUsers.map((user) => <div key={user.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/10 p-4">
              <div><b>{user.email}</b><p className="text-xs text-muted-foreground">User #{user.id} · {user.created_at ? new Date(user.created_at).toLocaleDateString() : "Date unavailable"}</p></div>
              <select aria-label={`Role for ${user.email}`} value={user.role} disabled={savingUser === user.id} onChange={(event) => void updateRole(user.id, event.target.value as UserRole)} className="rounded-xl border bg-background p-2 text-sm">
                {roles.map((role) => <option key={role} value={role}>{role.replaceAll("_", " ")}</option>)}
              </select>
            </div>)}
            {!filteredUsers.length && <p className="text-sm text-muted-foreground">No users match this search.</p>}
          </div>
        </section>

        <section className="glass-panel mt-6 rounded-[2rem] p-6">
          <h2 className="text-xl font-semibold">Audit trail</h2>
          <form onSubmit={(event) => void applyAuditFilters(event)} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <input aria-label="Audit search" value={auditSearch} onChange={(event) => setAuditSearch(event.target.value)} placeholder="Search actions, details, users" className="rounded-xl border border-white/10 bg-background px-3 py-2 text-sm" />
            <select aria-label="Filter audit by role" value={auditRole} onChange={(event) => setAuditRole(event.target.value)} className="rounded-xl border bg-background px-3 py-2 text-sm">
              <option value="">All roles</option>{roles.map((role) => <option key={role} value={role}>{role.replaceAll("_", " ")}</option>)}
            </select>
            <input aria-label="Filter audit by action" value={auditAction} onChange={(event) => setAuditAction(event.target.value)} placeholder="Action contains…" className="rounded-xl border border-white/10 bg-background px-3 py-2 text-sm" />
            <input aria-label="Filter audit by entity" value={auditEntity} onChange={(event) => setAuditEntity(event.target.value)} placeholder="Entity type contains…" className="rounded-xl border border-white/10 bg-background px-3 py-2 text-sm" />
            <label className="text-xs text-muted-foreground">From<input aria-label="Audit start date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="mt-1 block w-full rounded-xl border bg-background px-3 py-2 text-sm" /></label>
            <label className="text-xs text-muted-foreground">Through<input aria-label="Audit end date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="mt-1 block w-full rounded-xl border bg-background px-3 py-2 text-sm" /></label>
            <div className="flex gap-2 sm:col-span-2 lg:col-span-3"><Button type="submit" disabled={filtering}>{filtering ? "Filtering…" : "Apply filters"}</Button><Button type="button" variant="outline" onClick={() => void clearAuditFilters()} disabled={filtering}>Clear</Button></div>
          </form>
          <div className="mt-5 max-h-[520px] space-y-2 overflow-auto">
            {audit.map((entry) => <details key={entry.id} className="rounded-xl border border-white/10 p-3 text-sm">
              <summary className="cursor-pointer"><b>{entry.action}</b><span className="text-muted-foreground"> · {entry.user_email || `User #${entry.user_id ?? "unknown"}`} ({entry.role || "role unavailable"}) · {entry.entity_type}{entry.entity_id ? ` #${entry.entity_id}` : ""} · {entry.created_at ? new Date(entry.created_at).toLocaleString() : "Date unavailable"}</span></summary>
              {entry.details && <pre className="mt-3 overflow-x-auto rounded-lg bg-black/10 p-3 text-xs">{JSON.stringify(entry.details, null, 2)}</pre>}
            </details>)}
            {!audit.length && <p className="text-sm text-muted-foreground">No audit entries match these filters.</p>}
          </div>
        </section>
      </>}
    </DashboardLayout>
  )
}

export default function AdminPage() {
  return <RoleGuard allowedRoles={["admin"]}><AdminDashboard /></RoleGuard>
}
