"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Shield, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { apiFetch } from "@/lib/api"

export default function RegisterPage(){
  const router=useRouter()
  const [email,setEmail]=useState("")
  const [password,setPassword]=useState("")
  const [confirm,setConfirm]=useState("")
  const [error,setError]=useState("")
  const [busy,setBusy]=useState(false)
  const submit=async(e:React.FormEvent)=>{
    e.preventDefault();setError("")
    if(password!==confirm){setError("Passwords do not match");return}
    setBusy(true)
    try{
      const r=await apiFetch("/auth/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password,role:"customer"})})
      const d=await r.json()
      if(!r.ok)throw new Error(d.error||"Registration failed")
      router.push("/login?registered=1")
    }catch(e){setError(e instanceof Error?e.message:"Registration failed")}finally{setBusy(false)}
  }
  return <main className="app-shell flex min-h-screen items-center justify-center p-6"><section className="glass-panel w-full max-w-md rounded-[2rem] p-8"><div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground"><Shield/></div><h1 className="mt-6 text-3xl font-semibold">Create your account</h1><p className="mt-2 text-sm text-muted-foreground">New to RiskSure? Create a customer account.</p><form onSubmit={submit} className="mt-8 space-y-5"><div><Label>Email</Label><Input className="mt-2 h-12" type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></div><div><Label>Password</Label><Input className="mt-2 h-12" type="password" minLength={8} value={password} onChange={e=>setPassword(e.target.value)} required/></div><div><Label>Confirm password</Label><Input className="mt-2 h-12" type="password" minLength={8} value={confirm} onChange={e=>setConfirm(e.target.value)} required/></div>{error&&<p className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}<Button className="h-12 w-full" disabled={busy}>{busy?<Loader2 className="animate-spin"/>:"Create account"}</Button></form><p className="mt-6 text-center text-sm text-muted-foreground">Already have an account? <a className="text-primary hover:underline" href="/login">Sign in</a></p></section></main>
}