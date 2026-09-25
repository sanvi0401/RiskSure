import { RoleGuard } from "@/components/auth/role-guard"

export default function UnderwriterDashboardPage() {
  return (
    <RoleGuard allowedRoles={["underwriter", "admin"]}>
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold">Underwriting Centre</h1>
        <p className="text-muted-foreground">Review risk scores, explanations, applications and human decisions.</p>
      </div>
    </RoleGuard>
  )
}
