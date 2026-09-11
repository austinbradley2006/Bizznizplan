export type Side = 'long' | 'short'

export type Emotion =
  | 'calm'
  | 'focused'
  | 'fomo'
  | 'revenge'
  | 'anxious'
  | 'confident'
  | 'bored'

export type TradeSource =
  | 'manual'
  | 'tradingview'
  | 'robinhood'
  | 'ibkr'
  | 'tradovate'
  | 'thinkorswim'
  | 'generic'
  | 'webhook'

export interface Trade {
  id: string
  date: string // yyyy-MM-dd
  symbol: string
  side: Side
  entry: number
  exit: number
  size: number
  pnl: number
  emotion: Emotion
  setup: string
  notes: string
  createdAt: string
  source?: TradeSource
  externalId?: string
}

export interface DayReflection {
  date: string
  mood: number // 1-5
  text: string
}

export interface JournalState {
  trades: Trade[]
  reflections: DayReflection[]
}

export interface ImportResult {
  added: Trade[]
  skipped: number
  errors: string[]
  source: TradeSource
}
