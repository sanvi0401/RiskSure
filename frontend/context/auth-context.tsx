"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { API_BASE_URL } from "@/lib/api"

export type UserRole = "customer" | "underwriter" | "claims_officer" | "provider" | "admin"
export interface AuthUser { id:number; email:string; role:UserRole; created_at?:string|null }
interface AuthContextType {
 user:AuthUser|null; token:string|null; isLoading:boolean
 login:(email:string,password:string)=>Promise<{type:"complete"|"totp"|"setup";user:AuthUser;challenge?:string;setupToken?:string}>
 verifyTotp:(challenge:string,code:string)=>Promise<void>
 verifyTotpSetup:(setupToken:string,code:string)=>Promise<string[]>
 logout:()=>void
 hasRole:(roles:UserRole|UserRole[])=>boolean
}
const AuthContext=createContext<AuthContextType|undefined>(undefined)
export function AuthProvider({children}:{children:ReactNode}){
 const [user,setUser]=useState<AuthUser|null>(null),[token,setToken]=useState<string|null>(null),[isLoading,setIsLoading]=useState(true)
 useEffect(()=>{const t=localStorage.getItem("risksure_access_token"),u=localStorage.getItem("risksure_user");if(t&&u){try{setToken(t);setUser(JSON.parse(u))}catch{localStorage.removeItem("risksure_access_token");localStorage.removeItem("risksure_user")}}setIsLoading(false)},[])
 const storeSession=(t:string,u:AuthUser)=>{setToken(t);setUser(u);localStorage.setItem("risksure_access_token",t);localStorage.setItem("risksure_user",JSON.stringify(u))}
 const login=async(email:string,password:string)=>{const r=await fetch(`${API_BASE_URL}/auth/login`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});const d=await r.json().catch(()=>null);if(!r.ok)throw new Error(d?.error||`Login failed (${r.status})`);if(!d)throw new Error("Backend returned an invalid login response");if(d.totp_setup_required)return{type:"setup" as const,user:d.user,setupToken:d.setup_token};if(d.requires_totp)return{type:"totp" as const,user:d.user,challenge:d.challenge_token};storeSession(d.access_token,d.user);return{type:"complete" as const,user:d.user}}
 const verifyTotp=async(challenge:string,code:string)=>{const r=await fetch(`${API_BASE_URL}/auth/login/verify-totp`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${challenge}`},body:JSON.stringify({code})});const d=await r.json().catch(()=>null);if(!r.ok)throw new Error(d?.error||`Authenticator verification failed (${r.status})`);if(!d?.access_token)throw new Error("Backend returned an invalid authentication response");storeSession(d.access_token,d.user)}
 const verifyTotpSetup=async(setupToken:string,code:string)=>{const r=await fetch(`${API_BASE_URL}/auth/totp/verify-setup`,{method:"POST",headers:{"Content-Type":"application/json",Authorization:`Bearer ${setupToken}`},body:JSON.stringify({code})});const d=await r.json();if(!r.ok)throw new Error(d.error||"Invalid authenticator code");storeSession(d.access_token,d.user);return d.recovery_codes as string[]}
 const logout=()=>{setToken(null);setUser(null);localStorage.removeItem("risksure_access_token");localStorage.removeItem("risksure_user")}
 const hasRole=(roles:UserRole|UserRole[])=>!!user&&(Array.isArray(roles)?roles:[roles]).includes(user.role)
 return <AuthContext.Provider value={{user,token,isLoading,login,verifyTotp,verifyTotpSetup,logout,hasRole}}>{children}</AuthContext.Provider>
}
export function useAuth(){const context=useContext(AuthContext);if(!context)throw new Error("useAuth must be used inside AuthProvider");return context}
