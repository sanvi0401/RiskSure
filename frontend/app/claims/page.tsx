import { RoleGuard } from "@/components/auth/role-guard"

export default function ClaimsDashboardPage() {
  return (
    <RoleGuard allowedRoles={["claims_officer", "admin"]}>
      <div className="space-y-4">
        <h1 className="text-3xl font-semibold">Claims Centre</h1>
        <p className="text-muted-foreground">Review claims, documents, OCR results and claim assessments.</p>
      </div>
    </RoleGuard>
  )
}
