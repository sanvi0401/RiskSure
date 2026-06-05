"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { KPICard } from "@/components/dashboard/kpi-card"
import { StatusBadge } from "@/components/ui/status-badge"
import { Button } from "@/components/ui/button"
import { API_ENDPOINTS } from "@/lib/api"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { FileText, CheckCircle, AlertTriangle, Plus, Loader2 } from "lucide-react"

interface Application {
  id: number
  name: string
  risk_score: number
  decision: string
  premium: number
}

// Mock data for demonstration
const mockApplications: Application[] = [
  { id: 1, name: "John Smith", risk_score: 0.35, decision: "Approved", premium: 6750 },
  { id: 2, name: "Sarah Johnson", risk_score: 0.72, decision: "Higher Premium", premium: 8600 },
  { id: 3, name: "Michael Brown", risk_score: 0.95, decision: "Manual Review", premium: 0 },
  { id: 4, name: "Emily Davis", risk_score: 0.28, decision: "Approved", premium: 6400 },
  { id: 5, name: "Robert Wilson", risk_score: 0.65, decision: "Higher Premium", premium: 8250 },
]

export default function DashboardPage() {
  const [applications, setApplications] = useState<Application[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchApplications = async () => {
      try {
        const response = await fetch(API_ENDPOINTS.applications)
        if (response.ok) {
          const data = await response.json()
          setApplications(data)
        } else {
          // Use mock data if API is not available
          setApplications(mockApplications)
        }
      } catch {
        // Use mock data if API fails
        setApplications(mockApplications)
      } finally {
        setIsLoading(false)
      }
    }

    fetchApplications()
  }, [])

  const totalApplications = applications.length
  const approvedCount = applications.filter((a) => a.decision === "Approved").length
  const manualReviewCount = applications.filter((a) => a.decision === "Manual Review").length

  return (
    <DashboardLayout title="Dashboard" subtitle="Overview of insurance applications">
      <div className="flex flex-col gap-6">
        <section className="glass-panel overflow-hidden rounded-[2rem] p-6 lg:p-8">
          <div className="grid gap-6 lg:grid-cols-[1.4fr_0.6fr] lg:items-end">
            <div>
              <div className="hero-badge">Portfolio pulse</div>
              <h2 className="mt-5 text-4xl font-semibold tracking-[-0.06em] text-foreground">
                View every application as a living risk story.
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
                Monitor outcomes, surface manual reviews, and launch new assessments from a cleaner, more cinematic control surface.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
              <div className="rounded-[1.5rem] border border-white/8 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Auto decisions</p>
                <p className="mt-3 text-2xl font-semibold tracking-[-0.05em] text-foreground">{approvedCount}</p>
              </div>
              <div className="rounded-[1.5rem] border border-white/8 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Cases in queue</p>
                <p className="mt-3 text-2xl font-semibold tracking-[-0.05em] text-foreground">{manualReviewCount}</p>
              </div>
              <div className="rounded-[1.5rem] border border-white/8 bg-white/5 p-4">
                <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Portfolio size</p>
                <p className="mt-3 text-2xl font-semibold tracking-[-0.05em] text-foreground">{totalApplications}</p>
              </div>
            </div>
          </div>
        </section>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <KPICard
            title="Total Applications"
            value={totalApplications}
            icon={FileText}
            trend="Intake flow in focus"
          />
          <KPICard
            title="Approved"
            value={approvedCount}
            icon={CheckCircle}
            trend="Low-friction decisions"
          />
          <KPICard
            title="Manual Review"
            value={manualReviewCount}
            icon={AlertTriangle}
            trend="Needs analyst attention"
          />
        </div>

        <div className="glass-panel rounded-[2rem] p-6 lg:p-8">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-[-0.05em] text-foreground">Recent Applications</h2>
              <p className="mt-1 text-sm text-muted-foreground">A high-clarity view of the latest submitted cases.</p>
            </div>
            <Link href="/new-application">
              <Button className="rounded-2xl bg-primary px-5 text-primary-foreground hover:bg-primary/90">
                <Plus className="mr-2 h-4 w-4" />
                New Application
              </Button>
            </Link>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center py-12 text-destructive">
              {error}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-muted-foreground">Name</TableHead>
                  <TableHead className="text-muted-foreground">Risk Score</TableHead>
                  <TableHead className="text-muted-foreground">Decision</TableHead>
                  <TableHead className="text-right text-muted-foreground">Premium</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {applications.map((application) => (
                  <TableRow key={application.id} className="border-white/6">
                    <TableCell className="font-medium text-foreground">
                      {application.name}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {(application.risk_score * 100).toFixed(0)}%
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={application.decision} />
                    </TableCell>
                    <TableCell className="text-right text-foreground">
                      {application.premium > 0
                        ? `$${application.premium.toLocaleString()}`
                        : "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </DashboardLayout>
  )
}
