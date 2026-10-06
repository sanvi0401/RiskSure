"use client"

import { useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"
import { getDashboardRoute, useAuth, UserRole } from "@/context/auth-context"

interface RoleGuardProps {
  allowedRoles: UserRole[]
  children: React.ReactNode
}

export function RoleGuard({ allowedRoles, children }: RoleGuardProps) {
  const { user, isLoading, signedOut, hasRole } = useAuth()
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    if (isLoading) return
    if (!user) {
      router.replace(signedOut ? "/signed-out" : `/login?next=${encodeURIComponent(pathname)}`)
      return
    }
    if (!hasRole(allowedRoles)) {
      router.replace(getDashboardRoute(user.role))
    }
  }, [isLoading, signedOut, user, hasRole, allowedRoles, router, pathname])

  if (isLoading || !user || !hasRole(allowedRoles)) {
    return <div className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground">Checking access…</div>
  }

  return <>{children}</>
}
