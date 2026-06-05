import { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface KPICardProps {
  title: string
  value: string | number
  icon: LucideIcon
  trend?: string
  className?: string
}

export function KPICard({ title, value, icon: Icon, trend, className }: KPICardProps) {
  return (
    <div
      className={cn(
        "metric-card aurora-ring overflow-hidden",
        className
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">{title}</p>
          <p className="mt-3 text-4xl font-semibold tracking-[-0.05em] text-foreground">{value}</p>
          {trend && (
            <p className="mt-2 text-sm text-primary">{trend}</p>
          )}
        </div>
        <div className="flex h-14 w-14 items-center justify-center rounded-[1.3rem] bg-white/8 text-primary shadow-[0_16px_32px_rgba(0,0,0,0.18)]">
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </div>
  )
}
