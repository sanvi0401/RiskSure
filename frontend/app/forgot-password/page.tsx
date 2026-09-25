"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Shield, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { API_BASE_URL } from "@/lib/api"

export default function ForgotPasswordPage(){
  const router=useRouter()
  const [email,setEmail]=useState("")
  const [code,setCode]=useState("")
  const [password,setPassword]=useState("")
  const [confirm,setConfirm]=useState("")
  const [error,setError]=useState("")
  const [success,setSuccess]=useState("")
  const [busy,setBusy]=useState(false)
  const submit=async(e:React.FormEvent)=>{
    e.preventDefault();setError("");setSuccess("")
    if(password!==confirm){setError("Passwords do not match");return}
    setBusy(true)
    try{
      const r=await fetch(API_BASE_URL+"/auth/password/reset-with-totp",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,code,new_password:password})})
      const d=await r.json()
      if(!r.ok)throw new Error(d.error||"Password reset failed")
      setSuccess("Password reset successfully. You can now sign in.")
      setTimeout(()=>router.push("/login"),800)
    }catch(e){setError(e instanceof Error?e.message:"Password reset failed")}finally{setBusy(false)}
  }
  return <main className="app-shell flex min-h-screen items-center justify-center p-6"><section className="glass-panel w-full max-w-md rounded-[2rem] p-8"><div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground"><Shield/></div><h1 className="mt-6 text-3xl font-semibold">Reset password</h1><p className="mt-2 text-sm text-muted-foreground">Enter the 6-digit code from Google Authenticator to reset your password.</p><form onSubmit={submit} className="mt-8 space-y-5"><div><Label>Email</Label><Input className="mt-2 h-12" type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></div><div><Label>Google Authenticator code</Label><Input className="mt-2 h-12 text-center text-xl tracking-[.4em]" inputMode="numeric" maxLength={6} value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,"").slice(0,6))} placeholder="000000" required/></div><div><Label>New password</Label><Input className="mt-2 h-12" type="password" minLength={8} value={password} onChange={e=>setPassword(e.target.value)} required/></div><div><Label>Confirm new password</Label><Input className="mt-2 h-12" type="password" minLength={8} value={confirm} onChange={e=>setConfirm(e.target.value)} required/></div>{error&&<p className="rounded-xl bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}{success&&<p className="rounded-xl bg-primary/10 p-3 text-sm">{success}</p>}<Button className="h-12 w-full" disabled={busy||code.length!==6}>{busy?<Loader2 className="animate-spin"/>:"Reset password"}</Button></form><p className="mt-6 text-center text-sm text-muted-foreground"><a className="text-primary hover:underline" href="/login">Back to sign in</a></p></section></main>
}