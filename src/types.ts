export type Side = 'long' | 'short'

export type Emotion =
  | 'calm'
  | 'focused'
  | 'fomo'
  | 'revenge'
  | 'anxious'
  | 'confident'
  | 'bored'

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
