"use client"

import Link from "next/link"
import { ArrowLeft, FileText, Layers, Network } from "lucide-react"
import { useAuth } from "@/context/auth-context"

export function CaseNavigation({ applicationId, current }: { applicationId: number; current: "application" | "evidence" | "graph" }) {
  const { hasRole } = useAuth()
  if (!hasRole(["underwriter", "admin"])) return null
  const pages = [
    { key: "application", label: "Application", href: `/underwriter/applications/${applicationId}`, icon: FileText },
    { key: "evidence", label: "Case evidence", href: `/case-intelligence?id=${applicationId}`, icon: Layers },
    { key: "graph", label: "Relationships", href: `/relationship-graph?application_id=${applicationId}`, icon: Network },
  ]
  return <nav aria-label="Case navigation" className="mb-5 flex flex-wrap items-center gap-2 border-b border-border pb-4 text-sm">
    <Link href={`/underwriter?case=${applicationId}`} className="mr-2 inline-flex items-center gap-2 py-2 text-primary hover:underline"><ArrowLeft className="h-4 w-4" />Back to queue</Link>
    {pages.map(page => <Link key={page.key} href={page.href} aria-current={current === page.key ? "page" : undefined} className={`inline-flex items-center gap-2 rounded-md px-3 py-2 ${current === page.key ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted/30"}`}><page.icon className="h-4 w-4" />{page.label}</Link>)}
  </nav>
}
