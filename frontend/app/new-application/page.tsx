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
import { ArrowRight, BadgeCheck } from "lucide-react"

export default function NewApplicationPage() {
  const router = useRouter()
  const { setApplicationData } = useApplication()
  const [name, setName] = useState("")
  const [age, setAge] = useState("")
  const [sex, setSex] = useState("")
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validate = () => {
    const newErrors: Record<string, string> = {}
    if (!name.trim()) newErrors.name = "Name is required"
    if (!age || parseInt(age) <= 0) newErrors.age = "Valid age is required"
    if (!sex) newErrors.sex = "Sex is required"
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleProceed = () => {
    if (validate()) {
      setApplicationData({
        name: name.trim(),
        age: parseInt(age),
        sex,
      })
      router.push("/risk")
    }
  }

  return (
    <DashboardLayout title="New Application" subtitle="Start a new insurance application">
      <div className="mx-auto max-w-5xl">
        <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
          <section className="metric-card">
            <div className="hero-badge">Applicant intake</div>
            <h2 className="mt-5 text-3xl font-semibold tracking-[-0.05em] text-foreground">Start with a profile that feels deliberate.</h2>
            <p className="mt-4 text-sm leading-7 text-muted-foreground">
              Capture the essential identity inputs first. The rest of the workflow will build risk, decision, and premium context around this profile.
            </p>

            <div className="mt-8 space-y-3">
              {[
                "Applicant identity anchors the full underwriting trail",
                "Structured intake reduces scoring friction later",
                "Responsive layout keeps the form easy on smaller screens",
              ].map((item) => (
                <div key={item} className="flex items-start gap-3 rounded-[1.3rem] border border-white/8 bg-white/5 px-4 py-3">
                  <BadgeCheck className="mt-0.5 h-4 w-4 text-primary" />
                  <p className="text-sm text-foreground">{item}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="glass-panel rounded-[2rem] p-8 lg:p-9">
            <h2 className="mb-6 text-2xl font-semibold tracking-[-0.04em] text-foreground">Applicant Information</h2>

            <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-2">
              <Label htmlFor="name" className="text-sm font-medium text-foreground">
                Full Name
              </Label>
              <Input
                id="name"
                placeholder="Enter applicant's full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-12 rounded-2xl border-white/10 bg-white/6"
              />
              {errors.name && <p className="text-sm text-destructive">{errors.name}</p>}
            </div>

            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <div className="flex flex-col gap-2">
                <Label htmlFor="age" className="text-sm font-medium text-foreground">
                  Age
                </Label>
                <Input
                  id="age"
                  type="number"
                  placeholder="Enter age"
                  value={age}
                  onChange={(e) => setAge(e.target.value)}
                  className="h-12 rounded-2xl border-white/10 bg-white/6"
                />
                {errors.age && <p className="text-sm text-destructive">{errors.age}</p>}
              </div>

              <div className="flex flex-col gap-2">
                <Label htmlFor="sex" className="text-sm font-medium text-foreground">
                  Sex
                </Label>
                <Select value={sex} onValueChange={setSex}>
                  <SelectTrigger className="h-12 rounded-2xl border-white/10 bg-white/6">
                    <SelectValue placeholder="Select sex" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="male">Male</SelectItem>
                    <SelectItem value="female">Female</SelectItem>
                  </SelectContent>
                </Select>
                {errors.sex && <p className="text-sm text-destructive">{errors.sex}</p>}
              </div>
            </div>

            <button
              type="button"
              onClick={(e) => {
                e.preventDefault()
                handleProceed()
              }}
              className="mt-4 flex h-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_45px_rgba(141,240,207,0.18)] hover:bg-primary/90"
            >
              Proceed to Risk Assessment
              <ArrowRight className="ml-2 h-4 w-4" />
            </button>
          </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  )
}
