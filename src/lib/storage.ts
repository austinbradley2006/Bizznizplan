import type { JournalState } from '../types'
import { seedState } from '../data/seed'

const KEY = 'daybook.journal.v1'

export function loadJournal(): JournalState {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) {
      const seed = seedState()
      localStorage.setItem(KEY, JSON.stringify(seed))
      return seed
    }
    return JSON.parse(raw) as JournalState
  } catch {
    return seedState()
  }
}

export function saveJournal(state: JournalState): void {
  localStorage.setItem(KEY, JSON.stringify(state))
}

export function resetJournal(): JournalState {
  const seed = seedState()
  localStorage.setItem(KEY, JSON.stringify(seed))
  return seed
}
