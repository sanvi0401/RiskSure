"use client"

import { usePathname } from "next/navigation"
import { Sidebar } from "./sidebar"
import { Header } from "./header"

interface DashboardLayoutProps {
  children: React.ReactNode
  title: string
  subtitle?: string
}

export function DashboardLayout({ children, title, subtitle }: DashboardLayoutProps) {
  const pathname = usePathname()

  return (
    <div className="app-shell">
      <div className="relative z-10 mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 py-4 lg:flex-row lg:gap-6 lg:px-6 lg:py-6">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col gap-6">
          <Header title={title} subtitle={subtitle} pathname={pathname} />
          <main className="relative">{children}</main>
        </div>
      </div>
    </div>
  )
}
