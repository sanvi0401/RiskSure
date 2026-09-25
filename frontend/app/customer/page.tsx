import { RoleGuard } from "@/components/auth/role-guard"

export default function CustomerDashboardPage() {
  return (
    <RoleGuard allowedRoles={["customer"]}>
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold">Customer Portal</h1>
        <p className="text-muted-foreground">Policies, claims, documents, coverage and premium information.</p>
      </div>
    </RoleGuard>
  )
}
