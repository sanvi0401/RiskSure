export interface UnderwritingApplication {
  id: number; name: string; age: number | null; bmi: number | null; smoker: string | null
  final_risk: number | null; decision: string | null; premium: number | null
  review_status: string; assigned_underwriter_id: number | null
  decision_reason?: string | null; created_at?: string | null
}
export type QueueView = "open" | "mine" | "unassigned" | "completed"
export type QueueSort = "oldest" | "newest" | "risk"

export function filterUnderwritingQueue(applications: UnderwritingApplication[], view: QueueView, userId: number | undefined, search = "", sort: QueueSort = "oldest") {
  const needle = search.trim().toLowerCase().replace(/^#/, "")
  return applications.filter(application => {
    const completed = application.review_status === "completed"
    if (view === "completed" ? !completed : completed) return false
    if (view === "mine" && application.assigned_underwriter_id !== userId) return false
    if (view === "unassigned" && application.assigned_underwriter_id !== null) return false
    return !needle || application.name.toLowerCase().includes(needle) || String(application.id).includes(needle)
  }).sort((a, b) => {
    if (sort === "risk") return (b.final_risk ?? -1) - (a.final_risk ?? -1) || a.id - b.id
    const first = a.created_at ? Date.parse(a.created_at) : a.id
    const second = b.created_at ? Date.parse(b.created_at) : b.id
    return (sort === "newest" ? -1 : 1) * (first - second || a.id - b.id)
  })
}
