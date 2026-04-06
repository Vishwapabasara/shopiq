import { clsx, type ClassValue } from 'clsx'

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs)
}

export function scoreColor(score: number): string {
  if (score >= 75) return 'text-emerald-600'
  if (score >= 50) return 'text-amber-500'
  return 'text-red-500'
}

export function scoreBg(score: number): string {
  if (score >= 75) return 'bg-emerald-50 border-emerald-200'
  if (score >= 50) return 'bg-amber-50 border-amber-200'
  return 'bg-red-50 border-red-200'
}

export function scoreLabel(score: number): string {
  if (score >= 80) return 'Excellent'
  if (score >= 65) return 'Good'
  if (score >= 50) return 'Needs work'
  if (score >= 30) return 'Poor'
  return 'Critical'
}

export function severityColor(s: string) {
  if (s === 'critical') return 'badge-critical'
  if (s === 'warning')  return 'badge-warning'
  return 'badge-info'
}

export function severityDot(s: string) {
  if (s === 'critical') return 'bg-red-500'
  if (s === 'warning')  return 'bg-amber-400'
  return 'bg-blue-400'
}

export function categoryLabel(cat: string): string {
  return { seo: 'SEO', content: 'Content', ux: 'UX', catalogue: 'Catalogue' }[cat] ?? cat
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
  })
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit',
  })
}

// Build a strokeDashoffset for an SVG circle score ring
// circle circumference = 2 * pi * r
export function ringOffset(score: number, radius = 54): number {
  const circ = 2 * Math.PI * radius
  return circ - (score / 100) * circ
}
