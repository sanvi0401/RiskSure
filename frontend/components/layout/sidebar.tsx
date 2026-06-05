"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  ArrowUpRight,
  LayoutDashboard,
  FilePlus,
  Activity,
  Scale,
  Calculator,
  FileText,
  Orbit,
  Shield,
} from "lucide-react"

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/new-application", label: "New Application", icon: FilePlus },
  { href: "/risk", label: "Risk Scoring", icon: Activity },
  { href: "/underwriting", label: "Underwriting", icon: Scale },
  { href: "/premium", label: "Premium", icon: Calculator },
  { href: "/final", label: "Final Review", icon: FileText },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="glass-panel relative z-20 w-full rounded-[2rem] p-4 lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)] lg:w-[290px] lg:self-start">
      <div className="flex items-center gap-4 rounded-[1.6rem] border border-white/8 bg-white/5 px-4 py-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-[1.2rem] bg-primary text-primary-foreground shadow-[0_16px_40px_rgba(141,240,207,0.22)]">
          <Shield className="h-6 w-6" />
        </div>
        <div>
          <p className="text-lg font-semibold tracking-[-0.03em] text-foreground">RiskSure</p>
          <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Cinematic underwriting</p>
        </div>
      </div>

      <div className="mt-5 rounded-[1.6rem] border border-primary/10 bg-primary/8 p-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-primary">
          <Orbit className="h-3.5 w-3.5" />
          Active scenario
        </div>
        <p className="mt-3 text-sm leading-6 text-foreground">
          A guided workspace for transforming applicant data into explainable decisions.
        </p>
      </div>

      <nav className="mt-5 flex flex-col gap-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center justify-between rounded-[1.2rem] border px-4 py-3.5 text-sm font-medium transition-all duration-200",
                isActive
                  ? "border-primary/25 bg-primary/12 text-foreground shadow-[0_18px_40px_rgba(4,12,19,0.16)]"
                  : "border-transparent bg-white/2 text-muted-foreground hover:border-white/10 hover:bg-white/6 hover:text-foreground"
              )}
            >
              <span className="flex items-center gap-3">
                <span className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-2xl transition",
                  isActive ? "bg-primary text-primary-foreground" : "bg-white/6 text-muted-foreground group-hover:bg-white/10 group-hover:text-foreground"
                )}>
                  <item.icon className="h-5 w-5" />
                </span>
                <span>{item.label}</span>
              </span>
              <ArrowUpRight className={cn("h-4 w-4 transition", isActive ? "text-primary" : "text-transparent group-hover:text-muted-foreground")} />
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
