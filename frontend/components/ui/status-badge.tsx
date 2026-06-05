import { cn } from "@/lib/utils"

type Status = "Approved" | "Higher Premium" | "Manual Review" | string

interface StatusBadgeProps {
  status: Status
  className?: string
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const getStatusStyles = (status: Status) => {
    switch (status) {
      case "Approved":
        return "border border-primary/25 bg-primary/12 text-primary"
      case "Higher Premium":
      case "Approved with Conditions":
        return "border border-amber-300/20 bg-amber-300/12 text-amber-200"
      case "Manual Review":
        return "border border-red-300/20 bg-red-400/12 text-red-200"
      default:
        return "border border-white/8 bg-white/5 text-muted-foreground"
    }
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3.5 py-1.5 text-xs font-semibold uppercase tracking-[0.16em]",
        getStatusStyles(status),
        className
      )}
    >
      {status}
    </span>
  )
}
