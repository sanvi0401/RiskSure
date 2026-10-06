"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { getDashboardRoute, useAuth, UserRole } from "@/context/auth-context"
import { LayoutDashboard, FilePlus, Activity, Scale, Calculator, FileText, Shield, ClipboardList, Network, Receipt, LogOut, Menu, X } from "lucide-react"
import { Button } from "@/components/ui/button"

const navItems: { href: string; label: string; icon: typeof LayoutDashboard; roles: UserRole[] }[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["customer", "underwriter", "claims_officer", "provider", "admin"] },
  { href: "/underwriter", label: "Underwriting", icon: Scale, roles: ["admin"] },
  { href: "/new-application", label: "New Application", icon: FilePlus, roles: ["customer", "underwriter", "admin"] },
  { href: "/risk", label: "Risk Scoring", icon: Activity, roles: ["customer", "underwriter", "admin"] },
  { href: "/claims", label: "Claims Centre", icon: ClipboardList, roles: ["claims_officer", "admin"] },
  { href: "/provider", label: "Provider Portal", icon: Network, roles: ["provider", "admin"] },
  { href: "/premium", label: "Billing Centre", icon: Calculator, roles: ["customer", "admin"] },
  { href: "/final", label: "Final Review", icon: FileText, roles: ["underwriter", "claims_officer", "admin"] },
  { href: "/fraud", label: "Fraud Investigation", icon: Network, roles: ["underwriter", "claims_officer", "admin"] },
  { href: "/policy", label: "Policy Centre", icon: Receipt, roles: ["customer", "underwriter", "claims_officer", "admin"] },
  { href: "/relationship-graph", label: "Relationship Graph", icon: Network, roles: ["underwriter", "claims_officer", "provider", "admin"] },
  { href: "/admin/graph", label: "System Graph", icon: Network, roles: ["admin"] },
]

export function Sidebar() {
  const pathname = usePathname()
  const { user, logout, isSigningOut, hasRole } = useAuth()
  const [open, setOpen] = useState(false)
  return <aside className="mb-5 w-full shrink-0 rounded-lg border border-border bg-background/60 p-3 lg:sticky lg:top-6 lg:mb-0 lg:flex lg:h-[calc(100vh-3rem)] lg:w-[250px] lg:flex-col lg:self-start">
    <div className="flex items-center justify-between gap-3 px-2 py-2">
      <Link href={user ? getDashboardRoute(user.role) : "/login"} className="flex min-w-0 items-center gap-3"><Shield className="h-7 w-7 shrink-0 text-primary" /><div><p className="text-lg font-semibold">RiskSure</p><p className="text-xs capitalize text-muted-foreground">{user?.role.replaceAll("_", " ")}</p></div></Link>
      <div className="flex gap-1 lg:hidden"><Button variant="ghost" size="icon" aria-label={open ? "Close navigation" : "Open navigation"} title="Navigation" aria-expanded={open} aria-controls="workspace-navigation" onClick={() => setOpen(value => !value)}>{open ? <X /> : <Menu />}</Button><Button variant="ghost" size="icon" aria-label="Sign out" title="Sign out" disabled={isSigningOut} onClick={() => void logout()}><LogOut /></Button></div>
    </div>
    <nav id="workspace-navigation" aria-label="Workspace navigation" className={cn("mt-4 min-h-0 flex-1 space-y-1 overflow-y-auto", open ? "block" : "hidden", "lg:block")}>
      {navItems.filter(item => hasRole(item.roles)).map(item => {
        const href = item.href === "/dashboard" && user ? getDashboardRoute(user.role) : item.href
        const label = item.href === "/dashboard" && user?.role === "underwriter" ? "Application queue" : item.label
        const active = pathname === href || (href !== "/admin" && pathname.startsWith(href + "/"))
        return <Link key={item.href} href={href} onClick={() => setOpen(false)} aria-current={active ? "page" : undefined} className={cn("flex items-center gap-3 rounded-md px-3 py-3 text-sm", active ? "bg-primary/10 font-medium text-primary" : "text-muted-foreground hover:bg-muted/30 hover:text-foreground")}><item.icon className="h-4 w-4 shrink-0" />{label}</Link>
      })}
    </nav>
    <Button variant="ghost" className="mt-4 hidden w-full justify-start border-t border-border pt-3 lg:flex" disabled={isSigningOut} onClick={() => void logout()}><LogOut className="h-4 w-4" />{isSigningOut ? "Signing out..." : "Sign out"}</Button>
  </aside>
}
