"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"

export interface ApplicationData {
  name: string
  age: number
  sex: string
  bmi: number
  children: number
  smoker: string
  region: string
  riskScore: number
  ruleAdjustment: number
  appliedRules: { rule: string; adjustment: number }[]
  finalRisk: number
  decision: string
  premium: number
  modelStatus: string
  explanation: {
    method: string
    features: { feature: string; contribution: number; direction: string }[]
  }
}

interface ApplicationContextType {
  applicationData: ApplicationData
  setApplicationData: (data: Partial<ApplicationData>) => void
  resetApplication: () => void
}

const defaultApplicationData: ApplicationData = {
  name: "",
  age: 0,
  sex: "",
  bmi: 0,
  children: 0,
  smoker: "",
  region: "",
  riskScore: 0,
  ruleAdjustment: 0,
  appliedRules: [],
  finalRisk: 0,
  decision: "",
  premium: 0,
  modelStatus: "",
  explanation: { method: "", features: [] },
}

const ApplicationContext = createContext<ApplicationContextType | undefined>(undefined)

const STORAGE_KEY = "risksure_application_draft"

export function ApplicationProvider({ children }: { children: ReactNode }) {
  const [applicationData, setApplicationDataState] = useState<ApplicationData>(defaultApplicationData)
  const [hydrated, setHydrated] = useState(false)

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY)
      if (raw) setApplicationDataState({ ...defaultApplicationData, ...JSON.parse(raw) })
    } catch {
      sessionStorage.removeItem(STORAGE_KEY)
    } finally {
      setHydrated(true)
    }
  }, [])

  useEffect(() => {
    if (!hydrated) return
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(applicationData))
    } catch {
      // Storage can be unavailable in privacy-restricted browser contexts.
    }
  }, [applicationData, hydrated])

  const setApplicationData = (data: Partial<ApplicationData>) => {
    setApplicationDataState((prev) => ({ ...prev, ...data }))
  }

  const resetApplication = () => {
    setApplicationDataState(defaultApplicationData)
    try { sessionStorage.removeItem(STORAGE_KEY) } catch {} 
  }

  return (
    <ApplicationContext.Provider value={{ applicationData, setApplicationData, resetApplication }}>
      {children}
    </ApplicationContext.Provider>
  )
}

export function useApplication() {
  const context = useContext(ApplicationContext)
  if (context === undefined) {
    throw new Error("useApplication must be used within an ApplicationProvider")
  }
  return context
}
