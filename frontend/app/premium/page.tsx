"use client"

import { useEffect, useState } from "react"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { RoleGuard } from "@/components/auth/role-guard"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { apiFetch, API_ENDPOINTS } from "@/lib/api"

type Policy = { id:number; policy_number:string; premium_amount:number; status:string }

export default function Page(){return <RoleGuard allowedRoles={["customer","admin"]}><B/></RoleGuard>}

function B(){
  const [a,setA]=useState<any[]>([])
  const [policies,setPolicies]=useState<Policy[]>([])
  const [policyId,setPolicyId]=useState("")
  const [m,setM]=useState("")

  const load=async()=>{
    try{
      const [billingResponse,policyResponse]=await Promise.all([
        apiFetch(API_ENDPOINTS.billing),
        apiFetch(API_ENDPOINTS.policies),
      ])
      const billing=await billingResponse.json().catch(()=>null)
      const policyData=await policyResponse.json().catch(()=>null)
      if(!billingResponse.ok)throw new Error(billing?.error||"Unable to load billing ("+billingResponse.status+")")
      if(!policyResponse.ok)throw new Error(policyData?.error||"Unable to load policies ("+policyResponse.status+")")
      setA(Array.isArray(billing)?billing:[])
      setPolicies(Array.isArray(policyData)?policyData:[])
    }catch(e){setM(e instanceof Error?e.message:"Unable to load billing")}
  }

  useEffect(() => { load() }, [])

  const create=async()=>{
    setM("")
    const selected=policies.find(x=>String(x.id)===policyId)
    if(!selected){setM("Select a policy before recording a payment");return}
    const x=await apiFetch(API_ENDPOINTS.billing,{
      method:"POST",
      body:JSON.stringify({policy_id:selected.id}),
    })
    const z=await x.json().catch(()=>null)
    setM(x.ok?"Transaction created: "+z?.reference:z?.error||"Failed ("+x.status+")")
    if(x.ok){setPolicyId("");load()}
  }

  return <DashboardLayout title="Billing Centre" subtitle="Premiums, transactions and payment records">
    <section className="glass-panel rounded-[2rem] p-6">
      <div className="flex gap-3">
        <select value={policyId} onChange={e=>setPolicyId(e.target.value)} className="h-10 flex-1 rounded-md border bg-background px-3 text-sm">
          <option value="">Select policy</option>
          {policies.filter(x=>Number(x.premium_amount)>0).map(x=><option key={x.id} value={x.id}>{x.policy_number} — premium ₹{Number(x.premium_amount).toLocaleString()}</option>)}
        </select>
        <Input value={policyId?String(policies.find(x=>String(x.id)===policyId)?.premium_amount||""):""} readOnly placeholder="Authoritative premium"/>
        <Button onClick={create} disabled={!policyId}>Record payment</Button>
      </div>
      {m&&<p className="mt-3 text-sm text-muted-foreground">{m}</p>}
      <div className="mt-6 space-y-3">{a.map(x=><div key={x.id} className="flex justify-between rounded-2xl border border-white/10 p-4"><div><b>{x.reference}</b><p className="text-xs text-muted-foreground">{x.transaction_type}</p></div><div className="text-right"><b>{"₹"+Number(x.amount||0).toLocaleString()}</b><p className="text-xs">{x.status}</p></div></div>)}</div>
    </section>
  </DashboardLayout>
}