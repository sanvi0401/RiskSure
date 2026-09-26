"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { useAuth, UserRole } from "@/context/auth-context"
import {
  ArrowUpRight, LayoutDashboard, FilePlus, Activity, Scale, Calculator, FileText, Orbit, Shield,
  ClipboardList, Network, Receipt, Users,
} from "lucide-react"

const navItems: { href: string; label: string; icon: typeof LayoutDashboard; roles: UserRole[] }[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["customer","underwriter","claims_officer","provider","admin"] },
  { href: "/new-application", label: "New Application", icon: FilePlus, roles: ["customer","underwriter","admin"] },
  { href: "/risk", label: "Risk Scoring", icon: Activity, roles: ["customer","underwriter","admin"] },
  { href: "/underwriting", label: "Underwriting", icon: Scale, roles: ["underwriter","admin"] },
  { href: "/claims", label: "Claims Centre", icon: ClipboardList, roles: ["claims_officer","admin"] },
  { href: "/provider", label: "Provider Portal", icon: Network, roles: ["provider","admin"] },
  { href: "/premium", label: "Billing Centre", icon: Calculator, roles: ["customer","underwriter","admin"] },
  { href: "/final", label: "Final Review", icon: FileText, roles: ["underwriter","claims_officer","admin"] },
  { href: "/fraud", label: "Fraud Investigation", icon: Network, roles: ["underwriter","claims_officer","admin"] },
  { href: "/policy", label: "Policy Centre", icon: Receipt, roles: ["customer","underwriter","claims_officer","admin"] },
  { href: "/admin", label: "Admin Centre", icon: Users, roles: ["admin"] },
]

export function Sidebar() {
  const pathname = usePathname()
  const { user, logout, hasRole } = useAuth()

  return (
    <aside className="glass-panel relative z-20 w-full rounded-[2rem] p-4 lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)] lg:w-[290px] lg:self-start">
      <div className="flex items-center gap-4 rounded-[1.6rem] border border-white/8 bg-white/5 px-4 py-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-[1.2rem] bg-primary text-primary-foreground"><Shield className="h-6 w-6" /></div>
        <div><p className="text-lg font-semibold tracking-[-0.03em] text-foreground">RiskSure</p><p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">{user?.role ?? "guest"}</p></div>
      </div>
      <div className="mt-5 rounded-[1.6rem] border border-primary/10 bg-primary/8 p-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-primary"><Orbit className="h-3.5 w-3.5" /> Active workspace</div>
        <p className="mt-3 text-sm leading-6 text-foreground">Access is filtered by your RiskSure role.</p>
      </div>
      <nav className="mt-5 flex flex-col gap-2">
        {navItems.filter(item => hasRole(item.roles)).map((item) => {
          const isActive = pathname === item.href
          return <Link key={item.href} href={item.href} className={cn("group flex items-center justify-between rounded-[1.2rem] border px-4 py-3.5 text-sm font-medium transition-all duration-200", isActive ? "border-primary/25 bg-primary/12 text-foreground" : "border-transparent bg-white/2 text-muted-foreground hover:border-white/10 hover:bg-white/6 hover:text-foreground")}>
            <span className="flex items-center gap-3"><span className={cn("flex h-10 w-10 items-center justify-center rounded-2xl", isActive ? "bg-primary text-primary-foreground" : "bg-white/6 text-muted-foreground")}><item.icon className="h-5 w-5" /></span><span>{item.label}</span></span>
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        })}
      </nav>
      <button onClick={logout} className="mt-5 w-full rounded-2xl border border-white/10 px-4 py-3 text-sm text-muted-foreground hover:bg-white/5 hover:text-foreground">Sign out</button>
    </aside>
  )
}
