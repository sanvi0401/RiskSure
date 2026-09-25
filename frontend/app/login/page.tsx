"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ArrowRight, Loader2, Shield, Sparkles, Waves } from "lucide-react"
import { useAuth } from "@/context/auth-context"\nimport { API_BASE_URL } from "@/lib/api"\nimport { QRCodeSVG } from "qrcode.react"

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")
  const { login } = useAuth()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    if (!email || !password) {
      setError("Please enter both email and password")
      setIsLoading(false)
      return
    }

    try {
      await login(email, password)
      router.push("/dashboard")
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Unable to sign in")
    } finally {
      setIsLoading(false)
    }
  }

  const submitTotp = async () => {
    setError("")
    setIsLoading(true)
    try {
      if (authStep === "setup") {
        const codes = await verifyTotpSetup(setupToken, code)
        setRecoveryCodes(codes)
      } else {
        await verifyTotp(challenge, code)
        router.push("/dashboard")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed")
    } finally {
      setIsLoading(false)
    }
  }

  if (authStep === "totp" || authStep === "setup") {
    return (
      <div className="app-shell flex min-h-screen items-center justify-center px-4 py-8">
        <section className="glass-panel w-full max-w-lg rounded-[2rem] p-8 lg:p-10">
          <div className="flex h-16 w-16 items-center justify-center rounded-[1.4rem] bg-primary text-primary-foreground">
            <Shield className="h-8 w-8" />
          </div>
          <h1 className="mt-6 text-3xl font-semibold tracking-[-0.05em] text-foreground">
            {authStep === "setup" ? "Set up Google Authenticator" : "Enter your authenticator code"}
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {authStep === "setup"
              ? "Scan this QR code with Google Authenticator, then enter the 6-digit code it generates."
              : "Open Google Authenticator and enter the current 6-digit RiskSure code."}
          </p>

          {authStep === "setup" && setupUri && (
            <div className="mt-8 flex flex-col items-center gap-5">
              <div className="rounded-3xl bg-white p-5">
                <QRCodeSVG value={setupUri} size={220} />
              </div>
              <div className="w-full rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Manual setup key</p>
                <p className="mt-2 break-all font-mono text-sm text-foreground">{setupSecret}</p>
              </div>
            </div>
          )}

          {recoveryCodes.length === 0 ? (
            <>
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                inputMode="numeric"
                maxLength={6}
                placeholder="000000"
                className="mt-8 h-14 rounded-2xl text-center text-2xl tracking-[0.5em]"
              />
              {error && <p className="mt-4 rounded-2xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}
              <Button onClick={submitTotp} disabled={isLoading || code.length !== 6} className="mt-6 h-12 w-full rounded-2xl bg-primary text-primary-foreground">
                {isLoading ? "Verifying..." : "Verify code"}
              </Button>
            </>
          ) : (
            <div className="mt-8">
              <p className="text-sm font-medium text-foreground">Save these recovery codes somewhere safe. Each can be used once.</p>
              <div className="mt-4 grid gap-2 rounded-2xl border border-white/10 bg-white/5 p-4">
                {recoveryCodes.map((item) => <code key={item} className="font-mono text-sm text-foreground">{item}</code>)}
              </div>
              <Button onClick={() => router.push("/dashboard")} className="mt-6 h-12 w-full rounded-2xl bg-primary text-primary-foreground">Continue to RiskSure</Button>
            </div>
          )}
        </section>
      </div>
    )
  }

  return (
    <div className="app-shell flex min-h-screen items-center justify-center px-4 py-8">
      <div className="relative z-10 grid w-full max-w-6xl gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="glass-panel overflow-hidden rounded-[2rem] p-8 lg:p-10">
          <div className="hero-badge">
            <Sparkles className="h-3.5 w-3.5" />
            Underwriting reimagined
          </div>

          <div className="mt-8 max-w-xl">
            <h1 className="text-5xl font-semibold tracking-[-0.07em] text-foreground lg:text-6xl">
              A calmer, sharper way to score risk.
            </h1>
            <p className="mt-5 text-base leading-8 text-muted-foreground">
              RiskSure turns raw applicant details into beautifully structured decisions with instant scoring, guided review, and premium clarity.
            </p>
          </div>

          <div className="mt-10 grid gap-4 md:grid-cols-3">
            <div className="metric-card">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Precision</p>
              <p className="mt-4 text-3xl font-semibold tracking-[-0.05em] text-foreground">ML + rules</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">Model-backed scoring layered with visible underwriting adjustments.</p>
            </div>
            <div className="metric-card">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Flow</p>
              <p className="mt-4 text-3xl font-semibold tracking-[-0.05em] text-foreground">7-step</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">A stepwise journey from applicant intake to final pricing review.</p>
            </div>
            <div className="metric-card">
              <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Mood</p>
              <p className="mt-4 text-3xl font-semibold tracking-[-0.05em] text-foreground">Control room</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">Designed to feel premium, cinematic, and clear under pressure.</p>
            </div>
          </div>

          <div className="mt-10 rounded-[1.8rem] border border-white/8 bg-white/5 p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-[1rem] bg-accent text-accent-foreground">
                <Waves className="h-6 w-6" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">Live design system refresh</p>
                <p className="text-sm text-muted-foreground">Glass surfaces, layered gradients, and stronger hierarchy across the full workflow.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="glass-panel rounded-[2rem] p-8 shadow-[0_30px_80px_rgba(0,0,0,0.25)] lg:p-10">
          <div className="mb-8 flex flex-col items-start">
            <div className="flex h-16 w-16 items-center justify-center rounded-[1.4rem] bg-primary text-primary-foreground shadow-[0_18px_45px_rgba(141,240,207,0.2)]">
              <Shield className="h-8 w-8" />
            </div>
            <h2 className="mt-6 text-3xl font-semibold tracking-[-0.05em] text-foreground">Enter the cockpit</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Sign in to manage intake, assess risk, and shape decisions with confidence.
            </p>
          </div>

          <form onSubmit={handleLogin} className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <Label htmlFor="email" className="text-sm font-medium text-foreground">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                placeholder="admin@risksure.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-12 rounded-2xl border-white/10 bg-white/6 px-4 text-foreground placeholder:text-muted-foreground"
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="password" className="text-sm font-medium text-foreground">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-12 rounded-2xl border-white/10 bg-white/6 px-4 text-foreground placeholder:text-muted-foreground"
              />
            </div>

            {error && (
              <p className="rounded-2xl border border-destructive/20 bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>
            )}

            <Button
              type="submit"
              disabled={isLoading}
              className="h-12 rounded-2xl bg-primary text-base font-semibold text-primary-foreground shadow-[0_18px_45px_rgba(141,240,207,0.18)] hover:bg-primary/90"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight className="ml-2 h-4 w-4" />
                </>
              )}
            </Button>
          </form>

          <div className="mt-8 rounded-[1.6rem] border border-white/8 bg-white/4 p-4">
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Demo access</p>
            <p className="mt-2 text-sm leading-6 text-foreground">Use an account created through the RiskSure authentication API.</p>
          </div>
        </section>
      </div>
    </div>
  )
}
