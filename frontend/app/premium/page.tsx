"use client"

import { useCallback, useEffect, useState } from "react"
import { Loader2, Plus, RefreshCw } from "lucide-react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuth } from "@/context/auth-context"
import { apiFetch, API_ENDPOINTS } from "@/lib/api"

type Policy = { id: number; customer_id: number; policy_number: string; premium_amount: number; status: string }
type Transaction = { id: number; policy_id: number | null; reference: string; transaction_type: string; amount: number; status: string }
const money = (value: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value || 0)

export default function Page() {
  return <RoleGuard allowedRoles={["customer", "admin"]}><BillingCentre /></RoleGuard>
}

function BillingCentre() {
  const { user } = useAuth()
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [policies, setPolicies] = useState<Policy[]>([])
  const [policyId, setPolicyId] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const selected = policies.find(policy => String(policy.id) === policyId)
  const payable = policies.filter(policy => policy.status === "active" && policy.premium_amount > 0 &&
    !transactions.some(transaction => transaction.policy_id === policy.id && transaction.transaction_type === "premium" && ["pending", "paid"].includes(transaction.status)))

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setError("")
    try {
      const [billingResponse, policyResponse] = await Promise.all([
        apiFetch(API_ENDPOINTS.billing, { signal }), apiFetch(API_ENDPOINTS.policies, { signal }),
      ])
      const billing = await billingResponse.json().catch(() => null)
      const policyData = await policyResponse.json().catch(() => null)
      if (!billingResponse.ok) throw new Error(billing?.error || "Unable to load billing")
      if (!policyResponse.ok) throw new Error(policyData?.error || "Unable to load policies")
      if (!Array.isArray(billing) || !Array.isArray(policyData)) throw new Error("Invalid billing response")
      if (!signal?.aborted) { setTransactions(billing); setPolicies(policyData) }
    } catch (caught) {
      if (!signal?.aborted) setError(caught instanceof Error ? caught.message : "Unable to load billing")
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  const create = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!selected || saving || !payable.some(policy => policy.id === selected.id)) return
    setSaving(true)
    setMessage("")
    setError("")
    try {
      const response = await apiFetch(API_ENDPOINTS.billing, {
        method: "POST", body: JSON.stringify({ policy_id: selected.id, ...(user?.role === "admin" ? { customer_id: selected.customer_id } : {}) }),
      })
      const data = await response.json().catch(() => null)
      if (!response.ok) throw new Error(data?.error || "Unable to create the premium transaction")
      if (!data?.reference) throw new Error("Invalid billing transaction response")
      setMessage(`Pending premium recorded: ${data.reference}. Payment is not confirmed.`)
      setPolicyId("")
      await load()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create the premium transaction")
    } finally {
      setSaving(false)
    }
  }

  return <DashboardLayout title="Billing Centre" subtitle="Premiums and transaction records">
    <section className="min-w-0">
      <h2 className="text-xl font-semibold">Premium transaction</h2>
      <form onSubmit={create} className="mt-5 grid items-end gap-3 md:grid-cols-[minmax(0,1fr)_180px_auto]">
        <div className="min-w-0"><Label htmlFor="billing-policy">Policy</Label>
          <select id="billing-policy" value={policyId} onChange={event => setPolicyId(event.target.value)} disabled={loading || saving} className="mt-2 h-10 w-full min-w-0 rounded-md border border-input bg-background px-3 text-sm">
            <option value="">Select policy</option>
            {payable.map(policy => <option key={policy.id} value={policy.id}>{policy.policy_number}</option>)}
          </select>
        </div>
        <div><Label htmlFor="billing-premium">Policy premium (USD)</Label><Input id="billing-premium" className="mt-2" value={selected ? money(selected.premium_amount) : ""} readOnly placeholder="$0.00" /></div>
        <Button type="submit" disabled={loading || saving || !selected || !payable.some(policy => policy.id === selected.id)}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}{saving ? "Recording..." : "Record pending premium"}
        </Button>
      </form>
      {!loading && !error && !payable.length && <p className="mt-3 text-sm text-muted-foreground">No active policies with an unrecorded premium.</p>}
      {message && <p role="status" className="mt-3 break-words text-sm text-primary">{message}</p>}
      {error && <p role="alert" className="mt-3 rounded-lg bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      <div className="mt-8 flex items-center justify-between gap-3 border-t border-border pt-5"><h2 className="text-xl font-semibold">Transactions</h2><Button variant="ghost" size="icon" title="Refresh transactions" aria-label="Refresh transactions" onClick={() => void load()} disabled={loading || saving}><RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /></Button></div>
      {loading ? <p role="status" className="mt-4 text-sm text-muted-foreground">Loading transactions...</p> :
        <div className="mt-4 space-y-3">
          {transactions.map(transaction => <article key={transaction.id} className="flex flex-wrap justify-between gap-3 rounded-lg border border-border p-4">
            <div className="min-w-0"><h3 className="break-all text-sm font-semibold">{transaction.reference}</h3><p className="mt-1 text-xs text-muted-foreground">{policies.find(policy => policy.id === transaction.policy_id)?.policy_number || "Unlinked transaction"} | {transaction.transaction_type}</p></div>
            <div className="text-right"><b className="text-sm">{money(transaction.amount)}</b><p className="mt-1 text-xs capitalize">{transaction.status}</p></div>
          </article>)}
          {!transactions.length && !error && <p className="text-sm text-muted-foreground">No transactions recorded.</p>}
        </div>}
    </section>
  </DashboardLayout>
}
