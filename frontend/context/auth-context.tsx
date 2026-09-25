"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { API_BASE_URL } from "@/lib/api"

export type UserRole = "customer" | "underwriter" | "claims_officer" | "provider" | "admin"

export interface AuthUser {
  id: number
  email: string
  role: UserRole
  created_at?: string | null
}

interface AuthContextType {
  user: AuthUser | null
  token: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  hasRole: (roles: UserRole | UserRole[]) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const storedToken = window.localStorage.getItem("risksure_access_token")
    const storedUser = window.localStorage.getItem("risksure_user")
    if (storedToken && storedUser) {
      try {
        setToken(storedToken)
        setUser(JSON.parse(storedUser))
      } catch {
        window.localStorage.removeItem("risksure_access_token")
        window.localStorage.removeItem("risksure_user")
      }
    }
    setIsLoading(false)
  }, [])

  const login = async (email: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || "Login failed")

    setToken(data.access_token)
    setUser(data.user)
    window.localStorage.setItem("risksure_access_token", data.access_token)
    window.localStorage.setItem("risksure_user", JSON.stringify(data.user))
  }

  const hasRole = (roles: UserRole | UserRole[]) => {\n    if (!user) return false\n    const allowed = Array.isArray(roles) ? roles : [roles]\n    return allowed.includes(user.role)\n  }\n\n  const logout = () => {
    setToken(null)
    setUser(null)
    window.localStorage.removeItem("risksure_access_token")
    window.localStorage.removeItem("risksure_user")
  }

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within AuthProvider")
  return context
}
