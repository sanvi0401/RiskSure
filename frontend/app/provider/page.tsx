import { RoleGuard } from "@/components/auth/role-guard"

export default function ProviderDashboardPage() {
  return (
    <RoleGuard allowedRoles={["provider", "admin"]}>
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold">Provider Portal</h1>
        <p className="text-muted-foreground">Eligibility, preauthorization, treatment and billing workflows.</p>
      </div>
    </RoleGuard>
  )
}
