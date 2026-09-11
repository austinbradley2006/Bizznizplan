import { format, isValid, parse, parseISO } from 'date-fns'
import type { ImportResult, Side, Trade, TradeSource } from '../types'
import { uid } from './stats'

type Row = Record<string, string>

function normalizeHeader(h: string): string {
  return h
    .trim()
    .toLowerCase()
    .replace(/^\uFEFF/, '')
    .replace(/[^a-z0-9%/#]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function parseCsv(text: string): { headers: string[]; rows: Row[] } {
  const lines: string[] = []
  let current = ''
  let inQuotes = false

  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    const next = text[i + 1]
    if (ch === '"') {
      if (inQuotes && next === '"') {
        current += '"'
        i++
      } else {
        inQuotes = !inQuotes
      }
      continue
    }
    if ((ch === '\n' || ch === '\r') && !inQuotes) {
      if (ch === '\r' && next === '\n') i++
      if (current.trim().length || lines.length) lines.push(current)
      current = ''
      continue
    }
    current += ch
  }
  if (current.length) lines.push(current)

  if (!lines.length) return { headers: [], rows: [] }

  const splitLine = (line: string): string[] => {
    const cells: string[] = []
    let cell = ''
    let q = false
    for (let i = 0; i < line.length; i++) {
      const ch = line[i]
      const next = line[i + 1]
      if (ch === '"') {
        if (q && next === '"') {
          cell += '"'
          i++
        } else q = !q
        continue
      }
      if (ch === ',' && !q) {
        cells.push(cell.trim())
        cell = ''
        continue
      }
      cell += ch
    }
    cells.push(cell.trim())
    return cells
  }

  const rawHeaders = splitLine(lines[0]).map(normalizeHeader)
  const rows: Row[] = []
  for (const line of lines.slice(1)) {
    if (!line.trim()) continue
    const cells = splitLine(line)
    const row: Row = {}
    rawHeaders.forEach((h, i) => {
      row[h] = cells[i] ?? ''
    })
    rows.push(row)
  }
  return { headers: rawHeaders, rows }
}

function pick(row: Row, aliases: string[]): string | undefined {
  for (const a of aliases) {
    const key = normalizeHeader(a)
    if (row[key] !== undefined && row[key] !== '') return row[key]
  }
  // fuzzy contains
  for (const [k, v] of Object.entries(row)) {
    if (!v) continue
    for (const a of aliases) {
      const n = normalizeHeader(a)
      if (k === n || k.includes(n) || n.includes(k)) return v
    }
  }
  return undefined
}

function parseNumber(raw?: string): number {
  if (!raw) return 0
  const cleaned = raw.replace(/[$,\s]/g, '').replace(/[()]/g, (m) => (m === '(' ? '-' : ''))
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : 0
}

function parseDate(raw?: string): string | null {
  if (!raw) return null
  const value = raw.trim()
  const iso = parseISO(value)
  if (isValid(iso) && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    return format(iso, 'yyyy-MM-dd')
  }

  const patterns = [
    'yyyy-MM-dd HH:mm:ss',
    'yyyy-MM-dd HH:mm',
    'yyyy-MM-dd',
    'MM/dd/yyyy HH:mm:ss',
    'MM/dd/yyyy HH:mm',
    'MM/dd/yyyy',
    'M/d/yyyy H:mm:ss',
    'M/d/yyyy H:mm',
    'M/d/yyyy',
    'dd/MM/yyyy HH:mm:ss',
    'dd/MM/yyyy',
    'yyyy/MM/dd HH:mm:ss',
    'yyyy/MM/dd',
  ]

  for (const p of patterns) {
    const d = parse(value, p, new Date())
    if (isValid(d)) return format(d, 'yyyy-MM-dd')
  }

  const fallback = new Date(value)
  if (isValid(fallback)) return format(fallback, 'yyyy-MM-dd')
  return null
}

function parseSide(raw?: string): Side | null {
  if (!raw) return null
  const s = raw.toLowerCase()
  if (/\bshort\b|\bsell\b|\bs\b/.test(s) && !/\blong\b/.test(s)) return 'short'
  if (/\blong\b|\bbuy\b|\bb\b/.test(s)) return 'long'
  if (s.includes('short') || s.includes('sell')) return 'short'
  if (s.includes('long') || s.includes('buy')) return 'long'
  return null
}

function fingerprint(t: Pick<Trade, 'date' | 'symbol' | 'side' | 'entry' | 'exit' | 'size' | 'pnl' | 'externalId'>): string {
  if (t.externalId) return `ext:${t.externalId}`
  return [t.date, t.symbol, t.side, t.entry, t.exit, t.size, t.pnl].join('|')
}

export function tradeFingerprint(t: Trade): string {
  return fingerprint(t)
}

function detectSource(headers: string[], preferred?: TradeSource): TradeSource {
  if (preferred && preferred !== 'generic') return preferred
  const h = headers.join(' | ')
  if (h.includes('trade #') || h.includes('cum profit') || (h.includes('type') && h.includes('contracts'))) {
    return 'tradingview'
  }
  if (h.includes('instrument') && h.includes('fill price')) return 'tradovate'
  if (h.includes('activity date') || h.includes('trans code')) return 'robinhood'
  if (h.includes('tradeDate') || h.includes('ib order') || h.includes('fifo pnl')) return 'ibkr'
  if (h.includes('exec time') || h.includes('os / ss')) return 'thinkorswim'
  return preferred ?? 'generic'
}

/** TradingView Strategy Tester "List of Trades" pairs Entry + Exit rows. */
function parseTradingViewList(rows: Row[], symbolFallback: string): Trade[] {
  type PartialTrade = {
    id: string
    side?: Side
    entry?: number
    exit?: number
    size?: number
    pnl?: number
    date?: string
    signal?: string
  }
  const byId = new Map<string, PartialTrade>()

  for (const row of rows) {
    const tradeNo = pick(row, ['Trade #', 'tradeNumber', 'Trade']) ?? ''
    const typeRaw = pick(row, ['Type', 'type']) ?? ''
    const type = typeRaw.toLowerCase()
    if (!type.includes('entry') && !type.includes('exit')) continue

    const side =
      parseSide(typeRaw) ??
      parseSide(pick(row, ['Signal', 'signal', 'Side', 'Direction'])) ??
      'long'
    const price = parseNumber(pick(row, ['Price USD', 'Price USDT', 'Price', 'price']))
    const qty = Math.abs(
      parseNumber(pick(row, ['Contracts', 'Position size (qty)', 'Qty', 'Quantity', 'Size'])),
    )
    const pnl = parseNumber(
      pick(row, ['Profit USD', 'Net P&L USD', 'Profit', 'Net P&L', 'P&L', 'PnL']),
    )
    const date = parseDate(pick(row, ['Date/Time', 'Date and time', 'dateTime', 'Date', 'Time']))
    const signal = pick(row, ['Signal', 'signal']) ?? ''
    const key = tradeNo || `${date}-${side}-${price}-${qty}`

    const cur = byId.get(key) ?? { id: key }
    cur.side = side
    cur.size = qty || cur.size
    if (signal) cur.signal = signal

    if (type.includes('entry')) {
      cur.entry = price
      if (date) cur.date = date
    }
    if (type.includes('exit')) {
      cur.exit = price
      cur.pnl = pnl
      if (date) cur.date = date
    }
    byId.set(key, cur)
  }

  const trades: Trade[] = []
  for (const [key, p] of byId) {
    if (p.entry === undefined && p.exit === undefined) continue
    const date = p.date ?? format(new Date(), 'yyyy-MM-dd')
    trades.push({
      id: uid(),
      date,
      symbol: symbolFallback || 'TV',
      side: p.side ?? 'long',
      entry: p.entry ?? 0,
      exit: p.exit ?? 0,
      size: p.size || 1,
      pnl: p.pnl ?? 0,
      emotion: 'focused',
      setup: p.signal || 'TradingView strategy',
      notes: `Imported from TradingView (trade ${key})`,
      createdAt: new Date().toISOString(),
      source: 'tradingview',
      externalId: `tv:${symbolFallback}:${key}`,
    })
  }
  return trades
}

function parseFlatRows(rows: Row[], source: TradeSource, defaultSymbol: string): Trade[] {
  const trades: Trade[] = []
  for (const row of rows) {
    const symbol = (
      pick(row, ['Symbol', 'Ticker', 'Instrument', 'Contract', 'Underlying', 'Asset']) ??
      defaultSymbol
    )
      .trim()
      .toUpperCase()
    if (!symbol) continue

    const side =
      parseSide(pick(row, ['Side', 'Direction', 'Type', 'Action', 'Buy/Sell', 'B/S'])) ?? 'long'
    const date =
      parseDate(
        pick(row, [
          'Date',
          'Trade Date',
          'Activity Date',
          'Exec Time',
          'Fill Time',
          'Date/Time',
          'Timestamp',
          'Close Date',
          'Exit Time',
        ]),
      ) ?? null
    if (!date) continue

    const entry = parseNumber(
      pick(row, ['Entry', 'Entry Price', 'Avg Entry', 'Open Price', 'Buy Price', 'Fill Price']),
    )
    const exit = parseNumber(
      pick(row, ['Exit', 'Exit Price', 'Avg Exit', 'Close Price', 'Sell Price', 'Price']),
    )
    const size =
      Math.abs(
        parseNumber(pick(row, ['Size', 'Qty', 'Quantity', 'Contracts', 'Filled Qty', 'Amount'])),
      ) || 1
    const pnl = parseNumber(
      pick(row, [
        'P&L',
        'PnL',
        'Profit',
        'Net P&L',
        'Net PnL',
        'FIFO P&L Realized',
        'Realized P&L',
        'Total',
        'Gain',
      ]),
    )
    const setup = pick(row, ['Setup', 'Strategy', 'Signal', 'Description', 'Notes']) ?? ''
    const idHint =
      pick(row, ['Id', 'ID', 'Order ID', 'Trade Id', 'Exec ID', 'Activity ID']) ??
      `${date}-${symbol}-${side}-${entry}-${exit}-${size}-${pnl}`

    trades.push({
      id: uid(),
      date,
      symbol,
      side,
      entry,
      exit,
      size,
      pnl,
      emotion: 'focused',
      setup: setup || sourceLabel(source),
      notes: `Imported from ${sourceLabel(source)}`,
      createdAt: new Date().toISOString(),
      source,
      externalId: `${source}:${idHint}`,
    })
  }
  return trades
}

function sourceLabel(source: TradeSource): string {
  const labels: Record<TradeSource, string> = {
    manual: 'Manual',
    tradingview: 'TradingView',
    robinhood: 'Robinhood',
    ibkr: 'Interactive Brokers',
    tradovate: 'Tradovate',
    thinkorswim: 'thinkorswim',
    generic: 'Broker CSV',
    webhook: 'TradingView webhook',
  }
  return labels[source]
}

export function mergeImportedTrades(existing: Trade[], incoming: Trade[]): ImportResult {
  const seen = new Set(existing.map(tradeFingerprint))
  const added: Trade[] = []
  let skipped = 0
  for (const t of incoming) {
    const fp = tradeFingerprint(t)
    if (seen.has(fp)) {
      skipped++
      continue
    }
    seen.add(fp)
    added.push(t)
  }
  return {
    added,
    skipped,
    errors: [],
    source: incoming[0]?.source ?? 'generic',
  }
}

export function importCsvText(
  text: string,
  options: { source?: TradeSource; symbol?: string } = {},
): ImportResult {
  const errors: string[] = []
  const { headers, rows } = parseCsv(text)
  if (!headers.length || !rows.length) {
    return { added: [], skipped: 0, errors: ['No rows found in CSV.'], source: options.source ?? 'generic' }
  }

  const source = detectSource(headers, options.source)
  const symbol = (options.symbol ?? '').trim().toUpperCase()

  let parsed: Trade[] = []
  try {
    if (source === 'tradingview') {
      parsed = parseTradingViewList(rows, symbol || 'TV')
      // If pairing failed (already-flat export), fall back
      if (!parsed.length) {
        parsed = parseFlatRows(rows, 'tradingview', symbol || 'TV')
      }
    } else {
      parsed = parseFlatRows(rows, source, symbol)
    }
  } catch (e) {
    errors.push(e instanceof Error ? e.message : 'Failed to parse CSV')
  }

  if (!parsed.length && !errors.length) {
    errors.push(
      'Could not map trade rows. Export List of Trades from TradingView, or a CSV with Date, Symbol, Side, and P&L columns.',
    )
  }

  return {
    added: parsed,
    skipped: 0,
    errors,
    source,
  }
}

/** TradingView alert webhook JSON (single trade or array). */
export function importWebhookPayload(
  raw: string,
  options: { symbol?: string } = {},
): ImportResult {
  const errors: string[] = []
  let data: unknown
  try {
    data = JSON.parse(raw)
  } catch {
    return {
      added: [],
      skipped: 0,
      errors: ['Invalid JSON. Paste a TradingView alert webhook payload.'],
      source: 'webhook',
    }
  }

  const items = Array.isArray(data) ? data : [data]
  const trades: Trade[] = []

  for (const item of items) {
    if (!item || typeof item !== 'object') continue
    const o = item as Record<string, unknown>
    const symbol = String(
      o.symbol ?? o.ticker ?? o.Symbol ?? options.symbol ?? 'TV',
    )
      .trim()
      .toUpperCase()
    const side = parseSide(String(o.side ?? o.action ?? o.strategy_action ?? 'long')) ?? 'long'
    const date =
      parseDate(String(o.date ?? o.time ?? o.timestamp ?? o.timenow ?? '')) ??
      format(new Date(), 'yyyy-MM-dd')
    const entry = Number(o.entry ?? o.price ?? o.open ?? 0) || 0
    const exit = Number(o.exit ?? o.close ?? o.price ?? 0) || 0
    const size = Math.abs(Number(o.size ?? o.qty ?? o.contracts ?? 1)) || 1
    const pnl = Number(o.pnl ?? o.profit ?? o.pl ?? 0) || 0
    const setup = String(o.setup ?? o.strategy ?? o.comment ?? 'TradingView alert')
    const externalId = String(o.id ?? o.orderId ?? `${date}-${symbol}-${side}-${entry}-${pnl}`)

    trades.push({
      id: uid(),
      date,
      symbol,
      side,
      entry,
      exit,
      size,
      pnl,
      emotion: 'focused',
      setup,
      notes: 'Imported from TradingView webhook JSON',
      createdAt: new Date().toISOString(),
      source: 'webhook',
      externalId: `webhook:${externalId}`,
    })
  }

  if (!trades.length) {
    errors.push('No trades found in JSON. Expected fields like symbol, side, pnl, date.')
  }

  return { added: trades, skipped: 0, errors, source: 'webhook' }
}

export const CONNECTION_GUIDES = [
  {
    id: 'tradingview' as const,
    title: 'TradingView',
    blurb: 'Import Strategy Tester List of Trades, or paste alert webhook JSON.',
    steps: [
      'Open Strategy Tester → List of Trades → Download CSV',
      'Optional: set alert webhook JSON with symbol, side, pnl, date',
      'Drop the CSV or paste JSON here — stats update immediately',
    ],
  },
  {
    id: 'robinhood' as const,
    title: 'Robinhood',
    blurb: 'Export account activity / trade history as CSV, then import.',
    steps: [
      'Robinhood → Account → Statements & History → Download CSV',
      'Or export from Robinhood Gold reports',
      'Import the file — Daybook maps Date, Symbol, Side, P&L when present',
    ],
  },
  {
    id: 'ibkr' as const,
    title: 'Interactive Brokers',
    blurb: 'Flex Query or Activity Statement CSV fills.',
    steps: [
      'Account Management → Reports → Flex Queries / Activity',
      'Export trades CSV',
      'Import here for calendar + win-rate tracking',
    ],
  },
  {
    id: 'tradovate' as const,
    title: 'Tradovate / NinjaTrader',
    blurb: 'Futures fill exports with instrument and P&L columns.',
    steps: [
      'Export fills or closed trades CSV from the platform',
      'Ensure Date, Instrument/Symbol, and P&L columns exist',
      'Import to merge into Daybook stats',
    ],
  },
  {
    id: 'generic' as const,
    title: 'Any broker CSV',
    blurb: 'Flexible mapper for Date, Symbol, Side, Entry, Exit, Size, P&L.',
    steps: [
      'Export closed trades from your broker',
      'Headers can vary — common aliases are auto-detected',
      'Duplicates are skipped on re-import',
    ],
  },
]
