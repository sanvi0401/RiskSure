"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { useApplication } from "@/context/application-context"
import { ArrowRight, ArrowLeft, DollarSign } from "lucide-react"

const BASE_PREMIUM = 5000

export default function PremiumPage() {
  const router = useRouter()
  const { applicationData } = useApplication()
  const [finalPremium, setFinalPremium] = useState(0)

  useEffect(() => {
    setFinalPremium(applicationData.premium)
  }, [applicationData.premium])

  return (
    <DashboardLayout title="Premium Calculation" subtitle="Calculate the final premium amount">
      <div className="mx-auto max-w-3xl">
        <div className="glass-panel rounded-[2rem] p-8">
          {applicationData.name && (
            <div className="mb-8 rounded-[1.5rem] border border-white/8 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Applicant</p>
              <p className="font-medium text-foreground">{applicationData.name}</p>
            </div>
          )}

          <div className="mb-8">
            <h3 className="mb-4 text-2xl font-semibold tracking-[-0.04em] text-foreground">Premium Breakdown</h3>
            <div className="rounded-[1.5rem] border border-white/8 bg-white/4">
              <div className="flex items-center justify-between border-b border-white/8 p-4">
                <span className="text-muted-foreground">Base Premium</span>
                <span className="font-medium text-foreground">${BASE_PREMIUM.toLocaleString()}</span>
              </div>
              <div className="flex items-center justify-between border-b border-white/8 p-4">
                <span className="text-muted-foreground">Risk Score Factor</span>
                <span className="font-medium text-foreground">
                  +{(applicationData.riskScore * 100).toFixed(0)}%
                </span>
              </div>
              <div className="flex items-center justify-between border-b border-white/8 p-4">
                <span className="text-muted-foreground">Rule Adjustment Factor</span>
                <span className="font-medium text-foreground">
                  +{(applicationData.ruleAdjustment * 100).toFixed(0)}%
                </span>
              </div>
              <div className="flex items-center justify-between bg-white/5 p-4">
                <span className="text-muted-foreground">Total Multiplier</span>
                <span className="font-medium text-foreground">
                  {(1 + applicationData.riskScore + applicationData.ruleAdjustment).toFixed(2)}x
                </span>
              </div>
            </div>
          </div>

          <div className="mb-8 flex flex-col items-center rounded-[1.8rem] border border-primary/20 bg-[radial-gradient(circle_at_top,rgba(141,240,207,0.18),rgba(89,200,255,0.08),transparent_75%)] p-8">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary">
              <DollarSign className="h-10 w-10 text-primary-foreground" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-muted-foreground">Final Premium</h2>
            <p className="mt-2 text-4xl font-bold text-primary">
              ${finalPremium.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
            <p className="mt-2 text-sm text-muted-foreground">Annual premium amount</p>
          </div>

          <div className="mb-8 rounded-[1.5rem] border border-white/8 bg-white/5 p-4">
            <p className="text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">Formula:</span>{" "}
              Final Premium = Base Premium x (1 + Risk Score + Rule Adjustment)
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              ${BASE_PREMIUM.toLocaleString()} x (1 + {applicationData.riskScore.toFixed(2)} + {applicationData.ruleAdjustment.toFixed(2)}) = ${finalPremium.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>

          <div className="flex justify-between">
            <Button
              variant="outline"
              onClick={() => router.push("/underwriting")}
              className="h-11 rounded-2xl border-white/10 bg-white/5"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Underwriting
            </Button>

            <Button
              onClick={() => router.push("/final")}
              className="h-11 rounded-2xl bg-primary text-primary-foreground hover:bg-primary/90"
            >
              Proceed to Final Review
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
