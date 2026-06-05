"use client"

import { Bell, Compass, Sparkles, User } from "lucide-react"
import { Button } from "@/components/ui/button"

interface HeaderProps {
  title: string
  subtitle?: string
  pathname: string
}

const flowSteps = [
  { href: "/new-application", label: "Profile" },
  { href: "/risk", label: "Risk" },
  { href: "/underwriting", label: "Decision" },
  { href: "/premium", label: "Premium" },
  { href: "/final", label: "Review" },
]

export function Header({ title, subtitle, pathname }: HeaderProps) {
  return (
    <header className="glass-panel rounded-[1.9rem] px-5 py-5 lg:px-7">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3">
          <div className="hero-badge">
            <Sparkles className="h-3.5 w-3.5" />
            Adaptive underwriting cockpit
          </div>
          <div>
            <h1 className="text-3xl font-semibold tracking-[-0.04em] text-foreground lg:text-4xl">
              {title}
            </h1>
            {subtitle && <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{subtitle}</p>}
          </div>
        </div>
        <div className="flex items-center gap-3 self-start">
          <Button variant="ghost" size="icon" className="rounded-2xl border border-white/8 bg-white/5 text-muted-foreground hover:bg-white/10 hover:text-foreground">
            <Bell className="h-5 w-5" />
          </Button>
          <div className="flex items-center gap-3 rounded-2xl border border-white/8 bg-white/6 px-3 py-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_10px_30px_rgba(141,240,207,0.2)]">
              <User className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">Operations Desk</p>
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">North star mode</p>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
        <div className="flex flex-wrap gap-2">
          {flowSteps.map((step, index) => {
            const activeIndex = flowSteps.findIndex((item) => item.href === pathname)
            const isActive = pathname === step.href
            const isComplete = activeIndex > index

            return (
              <div
                key={step.href}
                className={`rounded-full border px-4 py-2 text-xs font-medium uppercase tracking-[0.18em] transition ${
                  isActive
                    ? "border-primary/40 bg-primary/18 text-primary"
                    : isComplete
                      ? "border-accent/30 bg-accent/10 text-accent"
                      : "border-white/8 bg-white/4 text-muted-foreground"
                }`}
              >
                {step.label}
              </div>
            )
          })}
        </div>

        <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-muted-foreground">
            <Compass className="h-3.5 w-3.5" />
            Live posture
          </div>
          <p className="mt-2 text-sm text-foreground">Design tuned for clarity, motion, and decision confidence.</p>
        </div>
      </div>
    </header>
  )
}
