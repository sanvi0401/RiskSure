"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { useApplication } from "@/context/application-context"
import { API_ENDPOINTS, apiFetch } from "@/lib/api"
import { ArrowLeft, Save, Loader2, CheckCircle } from "lucide-react"

export default function FinalPage() {
  const router = useRouter()
  const { applicationData, resetApplication } = useApplication()
  const [isSaving, setIsSaving] = useState(false)
  const [isSaved, setIsSaved] = useState(false)

  const handleSave = async () => {
    setIsSaving(true)

    try {
      const payload = {
        name: applicationData.name,
        age: applicationData.age,
        sex: applicationData.sex,
        bmi: applicationData.bmi,
        children: applicationData.children,
        smoker: applicationData.smoker,
        region: applicationData.region,
        risk_score: applicationData.riskScore,
        rule_adjustment: applicationData.ruleAdjustment,
        final_risk: applicationData.finalRisk,
        decision: applicationData.decision,
        premium: applicationData.premium,
      }

      const response = await apiFetch(API_ENDPOINTS.save, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })

      if (response.ok) {
        setIsSaved(true)
        setTimeout(() => {
          resetApplication()
          router.push("/dashboard")
        }, 1500)
      } else {
        const data = await response.json().catch(() => ({}))
        throw new Error(data.error || "Unable to save application")
      }
    } catch (error) {
      console.error("Application save failed:", error)
      setError(error instanceof Error ? error.message : "Unable to save application")
    }
  }

  if (isSaved) {
    return (
      <DashboardLayout title="Application Saved" subtitle="Redirecting to dashboard">
        <div className="mx-auto max-w-3xl">
          <div className="glass-panel flex flex-col items-center justify-center rounded-[2rem] p-16">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-secondary">
              <CheckCircle className="h-10 w-10 text-primary" />
            </div>
            <h2 className="mt-6 text-2xl font-bold text-foreground">Application Saved Successfully!</h2>
            <p className="mt-2 text-muted-foreground">Redirecting to dashboard...</p>
          </div>
        </div>
      </DashboardLayout>
    )
  }

  return (
    <DashboardLayout title="Final Review" subtitle="Review and save the application">
      <div className="mx-auto max-w-3xl">
        <div className="glass-panel rounded-[2rem] p-8">
          <h2 className="mb-6 text-2xl font-semibold tracking-[-0.04em] text-foreground">Application Summary</h2>

          <div className="mb-6 rounded-[1.5rem] border border-white/8 bg-white/4">
            <div className="border-b border-white/8 bg-white/5 px-4 py-3">
              <h3 className="font-semibold text-foreground">Applicant Information</h3>
            </div>
            <div className="grid grid-cols-2 gap-4 p-4">
              <div>
                <p className="text-sm text-muted-foreground">Name</p>
                <p className="font-medium text-foreground">{applicationData.name || "-"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Age</p>
                <p className="font-medium text-foreground">{applicationData.age || "-"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Sex</p>
                <p className="font-medium capitalize text-foreground">{applicationData.sex || "-"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Region</p>
                <p className="font-medium capitalize text-foreground">{applicationData.region || "-"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">BMI</p>
                <p className="font-medium text-foreground">{applicationData.bmi || "-"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Children</p>
                <p className="font-medium text-foreground">{applicationData.children}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Smoker</p>
                <p className="font-medium capitalize text-foreground">{applicationData.smoker || "-"}</p>
              </div>
            </div>
          </div>

          <div className="mb-6 rounded-[1.5rem] border border-white/8 bg-white/4">
            <div className="border-b border-white/8 bg-white/5 px-4 py-3">
              <h3 className="font-semibold text-foreground">Risk Assessment</h3>
            </div>
            <div className="grid grid-cols-3 gap-4 p-4">
              <div className="text-center">
                <p className="text-sm text-muted-foreground">Risk Score</p>
                <p className="text-2xl font-bold text-foreground">
                  {(applicationData.riskScore * 100).toFixed(0)}%
                </p>
              </div>
              <div className="text-center">
                <p className="text-sm text-muted-foreground">Rule Adjustment</p>
                <p className="text-2xl font-bold text-foreground">
                  +{(applicationData.ruleAdjustment * 100).toFixed(0)}%
                </p>
              </div>
              <div className="text-center">
                <p className="text-sm text-muted-foreground">Final Risk</p>
                <p className="text-2xl font-bold text-primary">
                  {(applicationData.finalRisk * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          </div>

          <div className="mb-8 rounded-[1.5rem] border border-white/8 bg-white/4">
            <div className="border-b border-white/8 bg-white/5 px-4 py-3">
              <h3 className="font-semibold text-foreground">Decision & Premium</h3>
            </div>
            <div className="flex items-center justify-between p-4">
              <div>
                <p className="text-sm text-muted-foreground">Underwriting Decision</p>
                <div className="mt-2">
                  <StatusBadge status={applicationData.decision} className="px-3 py-1" />
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm text-muted-foreground">Final Premium</p>
                <p className="mt-1 text-3xl font-bold text-primary">
                  ${applicationData.premium.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
                <p className="text-xs text-muted-foreground">Annual</p>
              </div>
            </div>
          </div>

          <div className="flex justify-between">
            <Button
              variant="outline"
              onClick={() => router.push("/premium")}
              className="h-11 rounded-2xl border-white/10 bg-white/5"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Premium
            </Button>

            <Button
              onClick={handleSave}
              disabled={isSaving}
              className="h-11 rounded-2xl bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {isSaving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save Application
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
