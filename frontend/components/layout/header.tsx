"use client"

import { UserRound } from "lucide-react"
import { useAuth } from "@/context/auth-context"

interface HeaderProps { title: string; subtitle?: string; pathname: string }

export function Header({ title, subtitle }: HeaderProps) {
  const { user } = useAuth()
  return <header className="flex min-w-0 flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
    <div className="min-w-0"><p className="text-xs font-medium capitalize text-primary">{user?.role.replaceAll("_", " ")} workspace</p>
      <h1 className="mt-2 text-2xl font-semibold sm:text-3xl">{title}</h1>
      {subtitle && <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>}
    </div>
    <div className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground sm:max-w-64"><UserRound className="h-4 w-4 shrink-0" /><span className="break-all" title={user?.email}>{user?.email}</span></div>
  </header>
}
