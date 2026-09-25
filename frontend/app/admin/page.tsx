import { RoleGuard } from "@/components/auth/role-guard"

export default function AdminDashboardPage() {
  return (
    <RoleGuard allowedRoles={["admin"]}>
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold">Admin Centre</h1>
        <p className="text-muted-foreground">Users, policies, claims, investigations, models and audit controls.</p>
      </div>
    </RoleGuard>
  )
}
