"use client"

import { createContext, useContext, useState, ReactNode } from "react"

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
}

const ApplicationContext = createContext<ApplicationContextType | undefined>(undefined)

export function ApplicationProvider({ children }: { children: ReactNode }) {
  const [applicationData, setApplicationDataState] = useState<ApplicationData>(defaultApplicationData)

  const setApplicationData = (data: Partial<ApplicationData>) => {
    setApplicationDataState((prev) => ({ ...prev, ...data }))
  }

  const resetApplication = () => {
    setApplicationDataState(defaultApplicationData)
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
