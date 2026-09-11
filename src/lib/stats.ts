import { format, parseISO, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, getDay } from 'date-fns'
import type { Emotion, Trade } from '../types'

export function uid(): string {
  return crypto.randomUUID()
}

export function formatMoney(n: number, signed = true): string {
  const abs = Math.abs(n).toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  })
  if (!signed) return abs
  if (n > 0) return `+${abs}`
  if (n < 0) return `−${abs}`
  return abs
}

export function formatCompact(n: number): string {
  const sign = n > 0 ? '+' : n < 0 ? '−' : ''
  const abs = Math.abs(n)
  if (abs >= 1000) return `${sign}$${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}k`
  return `${sign}$${Math.round(abs)}`
}

export function pnlTone(n: number): 'up' | 'down' | 'flat' {
  if (n > 0) return 'up'
  if (n < 0) return 'down'
  return 'flat'
}

export interface Stats {
  netPnl: number
  winRate: number
  tradeCount: number
  wins: number
  losses: number
  avgWin: number
  avgLoss: number
  profitFactor: number
  bestDay: number
  worstDay: number
  expectancy: number
}

export function computeStats(trades: Trade[]): Stats {
  if (trades.length === 0) {
    return {
      netPnl: 0,
      winRate: 0,
      tradeCount: 0,
      wins: 0,
      losses: 0,
      avgWin: 0,
      avgLoss: 0,
      profitFactor: 0,
      bestDay: 0,
      worstDay: 0,
      expectancy: 0,
    }
  }

  const wins = trades.filter((t) => t.pnl > 0)
  const losses = trades.filter((t) => t.pnl < 0)
  const grossWin = wins.reduce((s, t) => s + t.pnl, 0)
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0))
  const byDay = dailyPnlMap(trades)
  const dayValues = Object.values(byDay)

  return {
    netPnl: trades.reduce((s, t) => s + t.pnl, 0),
    winRate: wins.length / trades.length,
    tradeCount: trades.length,
    wins: wins.length,
    losses: losses.length,
    avgWin: wins.length ? grossWin / wins.length : 0,
    avgLoss: losses.length ? -(grossLoss / losses.length) : 0,
    profitFactor: grossLoss === 0 ? (grossWin > 0 ? Infinity : 0) : grossWin / grossLoss,
    bestDay: dayValues.length ? Math.max(...dayValues) : 0,
    worstDay: dayValues.length ? Math.min(...dayValues) : 0,
    expectancy: trades.reduce((s, t) => s + t.pnl, 0) / trades.length,
  }
}

export function dailyPnlMap(trades: Trade[]): Record<string, number> {
  const map: Record<string, number> = {}
  for (const t of trades) {
    map[t.date] = (map[t.date] ?? 0) + t.pnl
  }
  return map
}

export function monthGrid(anchor: Date) {
  const start = startOfMonth(anchor)
  const end = endOfMonth(anchor)
  const days = eachDayOfInterval({ start, end })
  const lead = (getDay(start) + 6) % 7 // Monday-first
  return { start, end, days, lead, label: format(anchor, 'MMMM yyyy'), inMonth: (d: Date) => isSameMonth(d, anchor) }
}

export function tradesInMonth(trades: Trade[], anchor: Date): Trade[] {
  const key = format(anchor, 'yyyy-MM')
  return trades.filter((t) => t.date.startsWith(key))
}

export function emotionLabel(e: Emotion): string {
  const labels: Record<Emotion, string> = {
    calm: 'Calm',
    focused: 'Focused',
    fomo: 'FOMO',
    revenge: 'Revenge',
    anxious: 'Anxious',
    confident: 'Confident',
    bored: 'Bored',
  }
  return labels[e]
}

export function sortTrades(trades: Trade[]): Trade[] {
  return [...trades].sort((a, b) => {
    if (a.date !== b.date) return b.date.localeCompare(a.date)
    return b.createdAt.localeCompare(a.createdAt)
  })
}

export function todayKey(): string {
  return format(new Date(), 'yyyy-MM-dd')
}

export function parseDay(key: string): Date {
  return parseISO(key)
}
