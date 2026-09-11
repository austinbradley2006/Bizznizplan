import { useMemo, useRef, useState, type ChangeEvent } from 'react'
import { motion } from 'framer-motion'
import type { ImportResult, Trade, TradeSource } from '../types'
import {
  CONNECTION_GUIDES,
  importCsvText,
  importWebhookPayload,
  mergeImportedTrades,
} from '../lib/importTrades'

type Props = {
  trades: Trade[]
  onClose: () => void
  onImport: (trades: Trade[]) => void
}

const SAMPLE_TV = `Trade #,Type,Date/Time,Signal,Price USD,Contracts,Profit USD,Cum. Profit USD
1,Entry long,2026-09-08 09:35:00,ORB,21420,2,0,0
1,Exit long,2026-09-08 10:12:00,ORB,21455,2,1400,1400
2,Entry short,2026-09-09 11:02:00,VWAP fade,5788,1,0,1400
2,Exit short,2026-09-09 11:40:00,VWAP fade,5779,1,450,1850
`

export function ConnectionsModal({ trades, onClose, onImport }: Props) {
  const [source, setSource] = useState<TradeSource>('tradingview')
  const [symbol, setSymbol] = useState('NQ')
  const [webhookJson, setWebhookJson] = useState(
    '{\n  "symbol": "MNQ",\n  "side": "long",\n  "entry": 21400,\n  "exit": 21425,\n  "size": 2,\n  "pnl": 500,\n  "date": "2026-09-10",\n  "strategy": "TV alert"\n}',
  )
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [preview, setPreview] = useState<Trade[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  const guide = useMemo(
    () => CONNECTION_GUIDES.find((g) => g.id === source) ?? CONNECTION_GUIDES[0],
    [source],
  )

  function applyResult(parsed: ImportResult) {
    if (parsed.errors.length) {
      setError(parsed.errors.join(' '))
      setPreview([])
      setStatus(null)
      return
    }
    const merged = mergeImportedTrades(trades, parsed.added)
    setError(null)
    setPreview(merged.added)
    setStatus(
      merged.added.length
        ? `Ready to add ${merged.added.length} trade${merged.added.length === 1 ? '' : 's'}${
            merged.skipped ? ` (${merged.skipped} duplicate${merged.skipped === 1 ? '' : 's'} skipped)` : ''
          }.`
        : `No new trades — ${merged.skipped} duplicate${merged.skipped === 1 ? '' : 's'} already in Daybook.`,
    )
  }

  function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const text = String(reader.result ?? '')
      applyResult(importCsvText(text, { source, symbol }))
    }
    reader.onerror = () => setError('Could not read that file.')
    reader.readAsText(file)
    e.target.value = ''
  }

  function loadSample() {
    setSource('tradingview')
    applyResult(importCsvText(SAMPLE_TV, { source: 'tradingview', symbol }))
  }

  function parseWebhook() {
    applyResult(importWebhookPayload(webhookJson, { symbol }))
  }

  function confirmImport() {
    if (!preview.length) return
    onImport(preview)
    onClose()
  }

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-end justify-center bg-ink/45 p-3 sm:items-center sm:p-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-label="Connect TradingView and brokers"
        className="max-h-[92dvh] w-full max-w-2xl overflow-y-auto rounded-[28px] bg-cloud p-5 shadow-2xl sm:p-6"
        initial={{ opacity: 0, y: 28, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 18, scale: 0.98 }}
        transition={{ type: 'spring', stiffness: 320, damping: 28 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl tracking-tight">Connect & import</h2>
            <p className="mt-1 max-w-lg text-sm text-ink/55">
              Pull fills from TradingView and broker CSVs into the same calendar and stats.
              Live OAuth sync is not available yet — export → import keeps everything local.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full border border-line text-ink/50"
          >
            ×
          </button>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {CONNECTION_GUIDES.map((g) => (
            <button
              key={g.id}
              type="button"
              onClick={() => {
                setSource(g.id)
                setPreview([])
                setStatus(null)
                setError(null)
              }}
              className={[
                'rounded-full px-3.5 py-1.5 text-sm font-medium transition',
                source === g.id
                  ? 'bg-ink text-mist'
                  : 'border border-line text-ink/60 hover:border-ink/25',
              ].join(' ')}
            >
              {g.title}
            </button>
          ))}
        </div>

        <div className="rounded-[22px] border border-line bg-white/70 p-4">
          <div className="font-display text-lg tracking-tight">{guide.title}</div>
          <p className="mt-1 text-sm text-ink/55">{guide.blurb}</p>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-ink/70">
            {guide.steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <label className="block text-xs font-semibold tracking-wide text-ink/45 uppercase">
            <span className="mb-1.5 block">Default symbol (TradingView)</span>
            <input
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              className="w-full rounded-xl border border-line bg-white px-3 py-2 text-sm outline-none focus:border-sky-deep/40"
              placeholder="NQ"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="rounded-full bg-ink px-4 py-2.5 text-sm font-semibold text-mist"
            >
              Upload CSV
            </button>
            <button
              type="button"
              onClick={loadSample}
              className="rounded-full border border-line px-4 py-2.5 text-sm"
            >
              Try sample
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={onFile}
            />
          </div>
        </div>

        {source === 'tradingview' && (
          <div className="mt-5">
            <div className="mb-1.5 text-xs font-semibold tracking-wide text-ink/45 uppercase">
              Or paste TradingView webhook JSON
            </div>
            <textarea
              value={webhookJson}
              onChange={(e) => setWebhookJson(e.target.value)}
              rows={7}
              className="w-full resize-y rounded-2xl border border-line bg-white px-3 py-3 font-mono text-xs outline-none focus:border-sky-deep/40"
            />
            <button
              type="button"
              onClick={parseWebhook}
              className="mt-2 rounded-full border border-line px-4 py-2 text-sm"
            >
              Parse webhook
            </button>
          </div>
        )}

        {(status || error) && (
          <div
            className={[
              'mt-4 rounded-2xl px-3.5 py-3 text-sm',
              error ? 'bg-loss-soft text-loss' : 'bg-profit-soft text-ink/80',
            ].join(' ')}
          >
            {error ?? status}
          </div>
        )}

        {preview.length > 0 && (
          <div className="mt-4 overflow-hidden rounded-[22px] border border-line bg-white/80">
            <div className="border-b border-line px-3.5 py-2 text-xs font-semibold tracking-wide text-ink/45 uppercase">
              Preview ({preview.length})
            </div>
            <div className="max-h-48 overflow-y-auto">
              {preview.slice(0, 12).map((t) => (
                <div
                  key={t.id}
                  className="flex items-center justify-between gap-3 border-b border-line/70 px-3.5 py-2 text-sm last:border-0"
                >
                  <div className="min-w-0">
                    <span className="font-semibold">{t.symbol}</span>
                    <span className="text-ink/45"> · {t.date} · {t.side}</span>
                    <div className="truncate text-xs text-ink/45">{t.setup}</div>
                  </div>
                  <div className={t.pnl >= 0 ? 'tone-up font-semibold' : 'tone-down font-semibold'}>
                    {t.pnl >= 0 ? '+' : ''}
                    {t.pnl.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!preview.length}
            onClick={confirmImport}
            className="rounded-full bg-profit px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            Add to Daybook
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-line px-4 py-2.5 text-sm"
          >
            Cancel
          </button>
        </div>
      </motion.div>
    </motion.div>
  )
}
