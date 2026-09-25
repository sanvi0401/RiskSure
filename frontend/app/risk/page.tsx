"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useApplication } from "@/context/application-context"
import { apiJson, API_ENDPOINTS } from "@/lib/api"
import { ArrowRight, Loader2, Activity, AlertCircle, Sparkles } from "lucide-react"

export default function RiskPage() {
  const router = useRouter()
  const { applicationData, setApplicationData } = useApplication()
  const [bmi, setBmi] = useState("")
  const [children, setChildren] = useState("")
  const [smoker, setSmoker] = useState("")
  const [region, setRegion] = useState("")
  const [isCalculating, setIsCalculating] = useState(false)
  const [riskScore, setRiskScore] = useState<number | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const newErrors: Record<string, string> = {}
    if (!bmi || parseFloat(bmi) <= 0) newErrors.bmi = "Valid BMI is required"
    if (children === "" || parseInt(children) < 0) newErrors.children = "Valid number is required"
    if (!smoker) newErrors.smoker = "Smoker status is required"
    if (!region) newErrors.region = "Region is required"
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const calculateRisk = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!validate()) return

    setIsCalculating(true)
    try {
      const payload = {
        age: applicationData.age,
        sex: applicationData.sex,
        bmi: parseFloat(bmi),
        children: parseInt(children),
        smoker,
        region,
      }

      const data = await apiJson(API_ENDPOINTS.process, {
        method: "POST",
        body: JSON.stringify(payload),
      })

      {
        const appliedRules = []
        if (smoker === "yes") appliedRules.push({ rule: "Smoker = Yes", adjustment: 0.2 })
        if (parseFloat(bmi) > 30) appliedRules.push({ rule: "BMI > 30", adjustment: 0.05 })
        if (parseInt(children) > 2) appliedRules.push({ rule: "Children > 2", adjustment: 0.05 })
        setRiskScore(data.risk_score)
        setApplicationData({
          bmi: parseFloat(bmi),
          children: parseInt(children),
          smoker,
          region,
          riskScore: data.risk_score,
          ruleAdjustment: data.rule_adjustment,
          finalRisk: data.final_risk,
          decision: data.decision,
          premium: data.premium,
          appliedRules,
          modelStatus: data.model_status,
          explanation: data.explanation ?? { method: "", features: [] },
        })
      }
    } catch (error) {
      console.error("Risk calculation failed:", error)
      setErrors((current) => ({ ...current, api: "Risk calculation failed. Make sure the backend is running and you are signed in." }))
    } finally {
      setIsCalculating(false)
    }
  }

  return (
    <DashboardLayout title="Risk Assessment" subtitle="Calculate risk score for the applicant">
      <div className="mx-auto max-w-4xl">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="glass-panel rounded-[2rem] p-8">
            <h2 className="mb-6 text-2xl font-semibold tracking-[-0.04em] text-foreground">Risk Factors</h2>

            {applicationData.name && (
              <div className="mb-6 rounded-[1.5rem] border border-white/8 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Applicant</p>
                <p className="font-medium text-foreground">
                  {applicationData.name}, {applicationData.age} years old, {applicationData.sex}
                </p>
              </div>
            )}

            {errors.api && <div className="mb-4 rounded-2xl border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">{errors.api}</div>}\n\n            <form onSubmit={calculateRisk} className="flex flex-col gap-5">
              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <Label htmlFor="bmi" className="text-sm font-medium text-foreground">
                    BMI
                  </Label>
                  <Input
                    id="bmi"
                    type="number"
                    step="0.1"
                    placeholder="e.g., 25.5"
                    value={bmi}
                    onChange={(e) => setBmi(e.target.value)}
                    className="h-12 rounded-2xl border-white/10 bg-white/6"
                  />
                  {errors.bmi && <p className="text-xs text-destructive">{errors.bmi}</p>}
                </div>

                <div className="flex flex-col gap-2">
                  <Label htmlFor="children" className="text-sm font-medium text-foreground">
                    Children
                  </Label>
                  <Input
                    id="children"
                    type="number"
                    placeholder="e.g., 2"
                    value={children}
                    onChange={(e) => setChildren(e.target.value)}
                    className="h-12 rounded-2xl border-white/10 bg-white/6"
                  />
                  {errors.children && <p className="text-xs text-destructive">{errors.children}</p>}
                </div>
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="smoker" className="text-sm font-medium text-foreground">
                  Smoker
                </Label>
                <Select value={smoker} onValueChange={setSmoker}>
                  <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-white/6">
                    <SelectValue placeholder="Select smoker status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="yes">Yes</SelectItem>
                    <SelectItem value="no">No</SelectItem>
                  </SelectContent>
                </Select>
                {errors.smoker && <p className="text-xs text-destructive">{errors.smoker}</p>}
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="region" className="text-sm font-medium text-foreground">
                  Region
                </Label>
                <Select value={region} onValueChange={setRegion}>
                  <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-white/6">
                    <SelectValue placeholder="Select region" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="northeast">Northeast</SelectItem>
                    <SelectItem value="northwest">Northwest</SelectItem>
                    <SelectItem value="southeast">Southeast</SelectItem>
                    <SelectItem value="southwest">Southwest</SelectItem>
                  </SelectContent>
                </Select>
                {errors.region && <p className="text-xs text-destructive">{errors.region}</p>}
              </div>

              <Button
                type="submit"
                disabled={isCalculating}
                className="mt-2 h-12 rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_45px_rgba(141,240,207,0.18)] hover:bg-primary/90"
              >
                {isCalculating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Calculating...
                  </>
                ) : (
                  <>
                    <Activity className="mr-2 h-4 w-4" />
                    Calculate Risk
                  </>
                )}
              </Button>
            </form>
          </div>

          <div className="glass-panel rounded-[2rem] p-8">
            <h2 className="mb-6 text-2xl font-semibold tracking-[-0.04em] text-foreground">Risk Score Result</h2>

            {riskScore !== null ? (
              <div className="flex flex-col items-center justify-center py-8">
                <div className="flex h-36 w-36 items-center justify-center rounded-full border border-primary/30 bg-[radial-gradient(circle_at_center,rgba(141,240,207,0.2),rgba(89,200,255,0.08),transparent_72%)] shadow-[0_20px_60px_rgba(0,0,0,0.24)]">
                  <span className="text-4xl font-bold text-primary">
                    {(riskScore * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="mt-4 text-lg font-medium text-foreground">Risk Score</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Based on provided health factors
                </p>

                <div className="mt-8 w-full rounded-[1.5rem] border border-white/8 bg-white/5 p-4">
                  <h3 className="mb-3 text-sm font-semibold text-foreground">Rule Adjustments Preview</h3>
                  <ul className="flex flex-col gap-2 text-sm text-muted-foreground">
                    {smoker === "yes" && <li className="flex justify-between"><span>Smoker = Yes</span><span>+20%</span></li>}
                    {parseFloat(bmi) > 30 && <li className="flex justify-between"><span>BMI {">"} 30</span><span>+5%</span></li>}
                    {parseInt(children) > 2 && <li className="flex justify-between"><span>Children {">"} 2</span><span>+5%</span></li>}
                    {smoker !== "yes" && parseFloat(bmi) <= 30 && parseInt(children) <= 2 && (
                      <li className="text-center">No additional adjustments</li>
                    )}
                  </ul>
                </div>

                <Button
                  onClick={() => router.push("/underwriting")}
                  className="mt-6 h-12 w-full rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_45px_rgba(141,240,207,0.18)] hover:bg-primary/90"
                >
                  Proceed to Underwriting
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                <AlertCircle className="mb-4 h-12 w-12" />
                <p className="text-center">
                  Fill in the risk factors and calculate the risk score to proceed
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
