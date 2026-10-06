"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { ArrowRight, Check, Filter, Loader2, Network, RefreshCw, Users, X } from "lucide-react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AlertDialog, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog"
import { useAuth } from "@/context/auth-context"
import { apiFetch, apiJson, API_ENDPOINTS } from "@/lib/api"

type UserRole = "customer" | "underwriter" | "claims_officer" | "provider" | "admin"
type AdminView = "overview" | "workload" | "users" | "audit"
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
  applications: number
  pending_applications: number
  applications_under_review: number
  manual_review_applications: number
  approved_applications: number
  rejected_applications: number
  risk_distribution: { low: number; medium: number; high: number }
  underwriting_workload: { user_id: number; email: string; assigned_applications: number }[]
  claims: number
  policies: number
  providers_users: number
  providers: number
  billing_transactions: number
}

const roles: UserRole[] = ["customer", "underwriter", "claims_officer", "provider", "admin"]
const views: AdminView[] = ["overview", "workload", "users", "audit"]
const inputStyle = "min-w-0 rounded-lg border bg-background px-3 py-2 text-sm"

function AdminDashboard() {
  const { user: currentUser } = useAuth()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [audit, setAudit] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [view, setView] = useState<AdminView>("overview")
  const [queryReady, setQueryReady] = useState(false)
  const [savingUser, setSavingUser] = useState<number | null>(null)
  const [pendingRole, setPendingRole] = useState<{ user: AdminUser; role: UserRole } | null>(null)
  const [userSearch, setUserSearch] = useState("")
  const [auditSearch, setAuditSearch] = useState("")
  const [auditRole, setAuditRole] = useState("")
  const [auditAction, setAuditAction] = useState("")
  const [auditEntity, setAuditEntity] = useState("")
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [auditQuery, setAuditQuery] = useState("")
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
    setAudit(await apiJson<AuditEntry[]>(`${API_ENDPOINTS.adminAudit}${query ? `?${query}` : ""}`))
  }, [])

  useEffect(() => {
    const nextView = new URLSearchParams(window.location.search).get("view") as AdminView
    if (views.includes(nextView)) setView(nextView)
    setQueryReady(true)
    Promise.all([loadOverviewAndUsers(), loadAudit()])
      .catch((loadError) => setError(loadError instanceof Error ? loadError.message : "Unable to load admin data"))
      .finally(() => setLoading(false))
  }, [loadAudit, loadOverviewAndUsers])

  useEffect(() => {
    if (!queryReady) return
    const url = new URL(window.location.href)
    url.searchParams.set("view", view)
    window.history.replaceState(null, "", url)
  }, [queryReady, view])

  const filteredUsers = useMemo(() => {
    const needle = userSearch.trim().toLowerCase()
    return needle ? users.filter((user) => user.email.toLowerCase().includes(needle) || String(user.id) === needle) : users
  }, [userSearch, users])

  const refreshOverview = async () => {
    setLoading(true)
    setError("")
    try { await loadOverviewAndUsers() }
    catch (loadError) { setError(loadError instanceof Error ? loadError.message : "Unable to refresh admin data") }
    finally { setLoading(false) }
  }

  const updateRole = async () => {
    if (!pendingRole || savingUser !== null) return
    const { user, role } = pendingRole
    setSavingUser(user.id)
    setError("")
    setMessage("")
    try {
      const response = await apiFetch(API_ENDPOINTS.adminRole(user.id), { method: "PUT", body: JSON.stringify({ role }) })
      const result = await response.json().catch(() => null)
      if (!response.ok) throw new Error(result?.error || `Unable to update role (${response.status})`)
      setPendingRole(null)
      setMessage(`Role updated for ${user.email}.`)
      await Promise.all([loadOverviewAndUsers(), loadAudit(auditQuery)])
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Unable to update user role")
    } finally { setSavingUser(null) }
  }

  const applyAuditFilters = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError("")
    if (startDate && endDate && startDate > endDate) {
      setError("The start date must be on or before the end date.")
      return
    }
    setFiltering(true)
    const params = new URLSearchParams({ limit: "200" })
    if (auditSearch.trim()) params.set("search", auditSearch.trim())
    if (auditRole) params.set("role", auditRole)
    if (auditAction.trim()) params.set("action", auditAction.trim())
    if (auditEntity.trim()) params.set("entity_type", auditEntity.trim())
    if (startDate) params.set("start_date", startDate)
    if (endDate) params.set("end_date", endDate)
    try {
      await loadAudit(params.toString())
      setAuditQuery(params.toString())
    } catch (filterError) { setError(filterError instanceof Error ? filterError.message : "Unable to filter audit log") }
    finally { setFiltering(false) }
  }

  const clearAuditFilters = async () => {
    setFiltering(true)
    setError("")
    try {
      await loadAudit()
      setAuditQuery("")
      setAuditSearch(""); setAuditRole(""); setAuditAction(""); setAuditEntity(""); setStartDate(""); setEndDate("")
    } catch (filterError) { setError(filterError instanceof Error ? filterError.message : "Unable to load audit log") }
    finally { setFiltering(false) }
  }

  return (
    <DashboardLayout title="Admin Centre" subtitle="Organization metrics, account access, and audit records">
      {error && <div role="alert" className="mb-5 rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm">{error}</div>}
      {message && <p role="status" className="mb-5 flex items-center gap-2 text-sm"><Check className="h-4 w-4 shrink-0 text-emerald-500" />{message}</p>}
      {loading ? <div role="status" className="flex items-center justify-center gap-2 py-16"><Loader2 className="h-4 w-4 animate-spin" />Loading administration data...</div> : overview && (
        <Tabs value={view} onValueChange={(value) => setView(value as AdminView)}>
          <TabsList className="mb-6 grid h-auto w-full grid-cols-2 gap-1 sm:grid-cols-4">
            {views.map((item) => <TabsTrigger key={item} value={item} className="py-2 capitalize">{item}</TabsTrigger>)}
          </TabsList>
          <TabsContent value="overview" className="space-y-6">
            <div className="flex flex-wrap gap-2">
              <Button asChild><Link href="/underwriter">Review queue<ArrowRight className="ml-2 h-4 w-4" /></Link></Button>
              <Button variant="outline" onClick={() => setView("users")}><Users className="mr-2 h-4 w-4" />Manage access</Button>
              <Button variant="outline" asChild><Link href="/admin/graph"><Network className="mr-2 h-4 w-4" />System graph</Link></Button>
              <Button variant="outline" size="icon" aria-label="Refresh overview" title="Refresh overview" onClick={() => void refreshOverview()}><RefreshCw className="h-4 w-4" /></Button>
            </div>
            <section aria-label="Platform metrics" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Users", overview.users], ["Customers", overview.customers], ["Applications", overview.applications],
                ["Pending review", overview.pending_applications], ["Under review", overview.applications_under_review],
                ["Manual review", overview.manual_review_applications],
                ["Approved", overview.approved_applications], ["Rejected", overview.rejected_applications],
                ["Claims", overview.claims], ["Policies", overview.policies], ["Provider accounts", overview.providers_users],
                ["Providers", overview.providers], ["Billing transactions", overview.billing_transactions],
              ].map(([label, value]) => <div key={label} className="rounded-lg border p-4"><p className="text-sm text-muted-foreground">{label}</p><b className="mt-2 block text-2xl">{value}</b></div>)}
            </section>
            <section className="border-t pt-6">
              <h2 className="text-lg font-semibold">Risk distribution</h2>
              <div className="mt-4 grid grid-cols-3 gap-3">
                {(["low", "medium", "high"] as const).map((level) => <div key={level}><p className="text-sm capitalize text-muted-foreground">{level} risk</p><b className="mt-2 block text-2xl">{overview.risk_distribution[level]}</b></div>)}
              </div>
            </section>
          </TabsContent>
          <TabsContent value="workload">
            <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Underwriting workload</h2><Button variant="outline" asChild><Link href="/underwriter">Open application queue<ArrowRight className="ml-2 h-4 w-4" /></Link></Button></div>
            <div className="mt-4">
              {overview.underwriting_workload.length ? overview.underwriting_workload.map((item) => <div key={item.user_id} className="flex items-center justify-between gap-4 border-b py-4 text-sm"><span className="min-w-0 break-all">{item.email}</span><b className="shrink-0">{item.assigned_applications} open cases</b></div>) : <p className="text-sm text-muted-foreground">No underwriting assignments.</p>}
            </div>
          </TabsContent>
          <TabsContent value="users">
            <h2 className="text-lg font-semibold">Users and role management</h2>
            <input aria-label="Search users" value={userSearch} onChange={(event) => setUserSearch(event.target.value)} placeholder="Search by email or user ID" className={`mt-4 w-full sm:max-w-sm ${inputStyle}`} />
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              {filteredUsers.map((user) => <div key={user.id} className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
                <div className="min-w-0"><b className="break-all text-sm">{user.email}</b><p className="mt-1 text-xs text-muted-foreground">User #{user.id} | {user.created_at ? new Date(user.created_at).toLocaleDateString() : "Date unavailable"}</p></div>
                <select aria-label={`Role for ${user.email}`} value={user.role} disabled={savingUser !== null || user.id === currentUser?.id} onChange={(event) => { setError(""); setPendingRole({ user, role: event.target.value as UserRole }) }} className={inputStyle}>
                  {roles.map((role) => <option key={role} value={role}>{role.replaceAll("_", " ")}</option>)}
                </select>
              </div>)}
              {!filteredUsers.length && <p className="text-sm text-muted-foreground">No users match this search.</p>}
            </div>
          </TabsContent>
          <TabsContent value="audit">
            <h2 className="text-lg font-semibold">Audit trail</h2>
            <form onSubmit={(event) => void applyAuditFilters(event)} className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <input aria-label="Audit search" value={auditSearch} onChange={(event) => setAuditSearch(event.target.value)} placeholder="Search actions, details, users" className={inputStyle} />
              <select aria-label="Filter audit by role" value={auditRole} onChange={(event) => setAuditRole(event.target.value)} className={inputStyle}><option value="">All roles</option>{roles.map((role) => <option key={role} value={role}>{role.replaceAll("_", " ")}</option>)}</select>
              <input aria-label="Filter audit by action" value={auditAction} onChange={(event) => setAuditAction(event.target.value)} placeholder="Action contains..." className={inputStyle} />
              <input aria-label="Filter audit by entity" value={auditEntity} onChange={(event) => setAuditEntity(event.target.value)} placeholder="Entity type contains..." className={inputStyle} />
              <label className="min-w-0 text-xs text-muted-foreground">From<input aria-label="Audit start date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className={`mt-1 block w-full ${inputStyle}`} /></label>
              <label className="min-w-0 text-xs text-muted-foreground">Through<input aria-label="Audit end date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className={`mt-1 block w-full ${inputStyle}`} /></label>
              <div className="flex gap-2 sm:col-span-2 lg:col-span-3"><Button type="submit" disabled={filtering}>{filtering ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Filter className="mr-2 h-4 w-4" />}Apply filters</Button><Button type="button" variant="outline" onClick={() => void clearAuditFilters()} disabled={filtering}><X className="mr-2 h-4 w-4" />Clear</Button></div>
            </form>
            <div className="mt-5 max-h-[520px] space-y-2 overflow-auto">
              {audit.map((entry) => <details key={entry.id} className="break-words rounded-lg border p-3 text-sm">
                <summary className="cursor-pointer"><b>{entry.action}</b><span className="text-muted-foreground"> | {entry.user_email || `User #${entry.user_id ?? "unknown"}`} ({entry.role || "role unavailable"}) | {entry.entity_type}{entry.entity_id ? ` #${entry.entity_id}` : ""} | {entry.created_at ? new Date(entry.created_at).toLocaleString() : "Date unavailable"}</span></summary>
                {entry.details && <pre className="mt-3 overflow-x-auto rounded-lg bg-muted/30 p-3 text-xs">{JSON.stringify(entry.details, null, 2)}</pre>}
              </details>)}
              {!audit.length && <p className="text-sm text-muted-foreground">No audit entries match these filters.</p>}
            </div>
          </TabsContent>
        </Tabs>
      )}
      <AlertDialog open={!!pendingRole} onOpenChange={(open) => { if (!open && savingUser === null) setPendingRole(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader><AlertDialogTitle>Confirm account role change</AlertDialogTitle><AlertDialogDescription className="break-words">{pendingRole?.user.email}: {pendingRole?.user.role.replaceAll("_", " ")} to {pendingRole?.role.replaceAll("_", " ")}. Existing sessions for this account will be revoked.</AlertDialogDescription></AlertDialogHeader>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <AlertDialogFooter><AlertDialogCancel disabled={savingUser !== null}>Cancel</AlertDialogCancel><Button disabled={savingUser !== null} onClick={() => void updateRole()}>{savingUser !== null && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Confirm change</Button></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </DashboardLayout>
  )
}

export default function AdminPage() {
  return <RoleGuard allowedRoles={["admin"]}><AdminDashboard /></RoleGuard>
}
