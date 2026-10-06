"use client"

import { createContext, useContext, useEffect, useRef, useState, ReactNode } from "react"
import { useRouter } from "next/navigation"
import { apiFetch } from "@/lib/api"

async function refreshAccessToken(): Promise<string | null> {
  const refresh = typeof window !== "undefined" ? localStorage.getItem("risksure_refresh_token") : null
  if (!refresh) return null
  try {
    const response = await apiFetch("/auth/refresh", {
      method: "POST",
      headers: { Authorization: "Bearer " + refresh },
    })
    const data = await response.json().catch(() => null)
    if (!response.ok || !data?.access_token || localStorage.getItem("risksure_refresh_token") !== refresh) return null
    localStorage.setItem("risksure_access_token", data.access_token)
    return data.access_token
  } catch {
    return null
  }
}

export type UserRole = "customer" | "underwriter" | "claims_officer" | "provider" | "admin"
export function getDashboardRoute(role: UserRole): string {
  switch (role) {
    case "customer":
      return "/customer"
    case "underwriter":
      return "/underwriter"
    case "claims_officer":
      return "/claims"
    case "provider":
      return "/provider"
    case "admin":
      return "/admin"
  }
}
export interface AuthUser { id:number; email:string; role:UserRole; created_at?:string|null }
interface AuthContextType {
 user:AuthUser|null; token:string|null; isLoading:boolean
 login:(email:string,password:string,role?:UserRole)=>Promise<{type:"complete"|"totp"|"setup";user:AuthUser;challenge?:string;setupToken?:string}>
 verifyTotp:(challenge:string,code:string)=>Promise<void>
 verifyRecovery:(challenge:string,code:string)=>Promise<void>
 verifyTotpSetup:(setupToken:string,code:string)=>Promise<string[]>
 logout:()=>Promise<void>
 isSigningOut:boolean; signedOut:boolean; signOutError:string
 hasRole:(roles:UserRole|UserRole[])=>boolean
}
const AuthContext=createContext<AuthContextType|undefined>(undefined)
export function AuthProvider({children}:{children:ReactNode}){
 const router=useRouter()
 const sessionEpoch=useRef(0)
 const [isSigningOut,setIsSigningOut]=useState(false),[signOutError,setSignOutError]=useState("")
 const [signedOut,setSignedOut]=useState(false)
 const [user,setUser]=useState<AuthUser|null>(null),[token,setToken]=useState<string|null>(null),[isLoading,setIsLoading]=useState(true)
 useEffect(()=>{let cancelled=false
  const epoch=sessionEpoch.current
  const restore=async()=>{
    const storedToken=localStorage.getItem("risksure_access_token")
    const storedUser=localStorage.getItem("risksure_user")
    if(!storedToken||!storedUser){if(!cancelled)setIsLoading(false);return}
    try{
      const check=async(token:string)=>apiFetch("/auth/me",{method:"GET",headers:{Authorization:"Bearer "+token}})
      let response=await check(storedToken)
      let activeToken=storedToken
      if(response.status===401){
        const refreshed=await refreshAccessToken()
        if(refreshed){activeToken=refreshed;response=await check(refreshed)}
      }
      const data=await response.json().catch(()=>null)
      if(cancelled||epoch!==sessionEpoch.current)return
      if(response.ok&&data?.user){
        if(!cancelled){setToken(activeToken);setUser(data.user);localStorage.setItem("risksure_user",JSON.stringify(data.user))}
      }else{
        localStorage.removeItem("risksure_access_token");localStorage.removeItem("risksure_refresh_token");localStorage.removeItem("risksure_user")
        if(!cancelled){setToken(null);setUser(null)}
      }
    }catch{
      if(cancelled||epoch!==sessionEpoch.current)return
      localStorage.removeItem("risksure_access_token")
      localStorage.removeItem("risksure_refresh_token")
      localStorage.removeItem("risksure_user")
      try{sessionStorage.clear()}catch{}
      if(!cancelled){setToken(null);setUser(null)}
    }finally{if(!cancelled)setIsLoading(false)}
  }
  restore()
  return()=>{cancelled=true}
},[])
 const storeSession=(t:string,u:AuthUser,refresh?:string)=>{sessionEpoch.current+=1;setSignedOut(false);setToken(t);setUser(u);localStorage.setItem("risksure_access_token",t);if(refresh)localStorage.setItem("risksure_refresh_token",refresh);localStorage.setItem("risksure_user",JSON.stringify(u))}
 const login=async(email:string,password:string,role?:UserRole)=>{const r=await apiFetch("/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password,role})});const d=await r.json().catch(()=>null);if(!r.ok)throw new Error(d?.error||`Login failed (${r.status})`);if(!d)throw new Error("Backend returned an invalid login response");if(d.totp_setup_required)return{type:"setup" as const,user:d.user,setupToken:d.setup_token};if(d.requires_totp)return{type:"totp" as const,user:d.user,challenge:d.challenge_token};storeSession(d.access_token,d.user,d.refresh_token);return{type:"complete" as const,user:d.user}}
 const verifyRecovery=async(challenge:string,code:string)=>{const r=await apiFetch("/auth/login/recovery",{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+challenge},body:JSON.stringify({recovery_code:code})});const d=await r.json().catch(()=>null);if(!r.ok)throw new Error(d?.error||"Recovery login failed");storeSession(d.access_token,d.user,d.refresh_token)}
 const verifyTotp=async(challenge:string,code:string)=>{const r=await apiFetch("/auth/login/verify-totp",{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${challenge}`},body:JSON.stringify({code})});const d=await r.json().catch(()=>null);if(!r.ok)throw new Error(d?.error||`Authenticator verification failed (${r.status})`);if(!d?.access_token)throw new Error("Backend returned an invalid authentication response");storeSession(d.access_token,d.user,d.refresh_token)}
 const verifyTotpSetup=async(setupToken:string,code:string)=>{const r=await apiFetch("/auth/totp/verify-setup",{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${setupToken}`},body:JSON.stringify({code})});const d=await r.json().catch(()=>null);if(!r.ok)throw new Error(d?.error||"Invalid authenticator code");if(!d?.access_token)throw new Error("Backend returned an invalid authentication response");storeSession(d.access_token,d.user,d.refresh_token);return d.recovery_codes as string[]}
 const logout=async()=>{
  if(isSigningOut)return
  const access=localStorage.getItem("risksure_access_token")
  sessionEpoch.current+=1
  setSignedOut(true);setIsSigningOut(true);setSignOutError("");setToken(null);setUser(null)
  localStorage.removeItem("risksure_access_token");localStorage.removeItem("risksure_refresh_token");localStorage.removeItem("risksure_user")
  try{sessionStorage.clear()}catch{}
  router.replace("/signed-out")
  try{
   if(access){const response=await apiFetch("/auth/logout",{method:"POST",headers:{Authorization:"Bearer "+access},keepalive:true});if(!response.ok&&response.status!==401)throw new Error("Server sign-out was not confirmed")}
  }catch{setSignOutError("You are signed out on this device. Server confirmation is unavailable.")}
  finally{setIsSigningOut(false)}
 }
 const hasRole=(roles:UserRole|UserRole[])=>!!user&&(Array.isArray(roles)?roles:[roles]).includes(user.role)
 // Remount workspace providers so sign-out also discards in-memory drafts.
 return <AuthContext.Provider key={signedOut ? "signed-out" : "active-session"} value={{user,token,isLoading,login,verifyTotp,verifyRecovery,verifyTotpSetup,logout,isSigningOut,signedOut,signOutError,hasRole}}>{children}</AuthContext.Provider>
}
export function useAuth(){const context=useContext(AuthContext);if(!context)throw new Error("useAuth must be used inside AuthProvider");return context}
