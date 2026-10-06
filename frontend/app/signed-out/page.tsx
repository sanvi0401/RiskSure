"use client"

import Link from "next/link"
import { ArrowRight, Loader2, ShieldCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/auth-context"

export default function SignedOutPage() {
  const { isSigningOut, signOutError } = useAuth()
  return <main className="app-shell flex min-h-screen items-center justify-center px-5 py-12">
    <section className="w-full max-w-md text-center">
      <ShieldCheck className="mx-auto h-14 w-14 text-primary" aria-hidden="true" />
      <p className="mt-5 text-lg font-semibold">RiskSure</p>
      <h1 className="mt-5 text-4xl font-semibold">Thank you</h1>
      <p className="mt-3 text-sm text-muted-foreground">You have signed out of RiskSure.</p>
      {signOutError && <p role="status" className="mt-4 text-sm text-amber-300">{signOutError}</p>}
      {isSigningOut ? <Button className="mt-8" disabled><Loader2 className="h-4 w-4 animate-spin" />Signing out...</Button> :
        <Button asChild className="mt-8"><Link href="/login">Sign in again<ArrowRight className="h-4 w-4" /></Link></Button>}
    </section>
  </main>
}
