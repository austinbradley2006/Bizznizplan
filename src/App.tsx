import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { addMonths, format, subMonths } from 'date-fns'
import { AnimatePresence, motion } from 'framer-motion'
import type { DayReflection, Emotion, Side, Trade } from './types'
import { loadJournal, resetJournal, saveJournal } from './lib/storage'
import {
  computeStats,
  dailyPnlMap,
  emotionLabel,
  formatCompact,
  formatMoney,
  monthGrid,
  pnlTone,
  sortTrades,
  todayKey,
  tradesInMonth,
  uid,
} from './lib/stats'

const EMOTIONS: Emotion[] = [
  'calm',
  'focused',
  'confident',
  'anxious',
  'fomo',
  'revenge',
  'bored',
]

type Draft = {
  date: string
  symbol: string
  side: Side
  entry: string
  exit: string
  size: string
  pnl: string
  emotion: Emotion
  setup: string
  notes: string
}

const emptyDraft = (): Draft => ({
  date: todayKey(),
  symbol: '',
  side: 'long',
  entry: '',
  exit: '',
  size: '1',
  pnl: '',
  emotion: 'focused',
  setup: '',
  notes: '',
})

export default function App() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [reflections, setReflections] = useState<DayReflection[]>([])
  const [month, setMonth] = useState(() => new Date())
  const [selectedDay, setSelectedDay] = useState(todayKey())
  const [formOpen, setFormOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<Draft>(emptyDraft)
  const [reflectionText, setReflectionText] = useState('')
  const [mood, setMood] = useState(3)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const state = loadJournal()
    setTrades(state.trades)
    setReflections(state.reflections)
    setReady(true)
  }, [])

  useEffect(() => {
    if (!ready) return
    saveJournal({ trades, reflections })
  }, [trades, reflections, ready])

  useEffect(() => {
    const found = reflections.find((r) => r.date === selectedDay)
    setReflectionText(found?.text ?? '')
    setMood(found?.mood ?? 3)
  }, [selectedDay, reflections])

  const monthTrades = useMemo(() => tradesInMonth(trades, month), [trades, month])
  const stats = useMemo(() => computeStats(monthTrades), [monthTrades])
  const dayMap = useMemo(() => dailyPnlMap(monthTrades), [monthTrades])
  const grid = useMemo(() => monthGrid(month), [month])
  const dayTrades = useMemo(
    () => sortTrades(trades.filter((t) => t.date === selectedDay)),
    [trades, selectedDay],
  )
  const allSorted = useMemo(() => sortTrades(trades).slice(0, 8), [trades])
  const dayPnl = dayMap[selectedDay] ?? 0

  function openNew(date = selectedDay) {
    setEditingId(null)
    setDraft({ ...emptyDraft(), date })
    setFormOpen(true)
  }

  function openEdit(trade: Trade) {
    setEditingId(trade.id)
    setDraft({
      date: trade.date,
      symbol: trade.symbol,
      side: trade.side,
      entry: String(trade.entry),
      exit: String(trade.exit),
      size: String(trade.size),
      pnl: String(trade.pnl),
      emotion: trade.emotion,
      setup: trade.setup,
      notes: trade.notes,
    })
    setFormOpen(true)
  }

  function saveTrade() {
    const symbol = draft.symbol.trim().toUpperCase()
    if (!symbol) return

    const next: Trade = {
      id: editingId ?? uid(),
      date: draft.date,
      symbol,
      side: draft.side,
      entry: Number(draft.entry) || 0,
      exit: Number(draft.exit) || 0,
      size: Number(draft.size) || 1,
      pnl: Number(draft.pnl) || 0,
      emotion: draft.emotion,
      setup: draft.setup.trim(),
      notes: draft.notes.trim(),
      createdAt: new Date().toISOString(),
    }

    setTrades((prev) =>
      editingId ? prev.map((t) => (t.id === editingId ? { ...next, createdAt: t.createdAt } : t)) : [next, ...prev],
    )
    setSelectedDay(next.date)
    setFormOpen(false)
  }

  function deleteTrade(id: string) {
    setTrades((prev) => prev.filter((t) => t.id !== id))
    if (editingId === id) setFormOpen(false)
  }

  function saveReflection() {
    setReflections((prev) => {
      const others = prev.filter((r) => r.date !== selectedDay)
      if (!reflectionText.trim()) return others
      return [...others, { date: selectedDay, mood, text: reflectionText.trim() }]
    })
  }

  function handleReset() {
    const state = resetJournal()
    setTrades(state.trades)
    setReflections(state.reflections)
    setSelectedDay(todayKey())
    setMonth(new Date())
  }

  if (!ready) {
    return (
      <div className="grid min-h-dvh place-items-center text-ink/50">
        Opening the book…
      </div>
    )
  }

  return (
    <div className="bg-noise relative min-h-dvh">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-[linear-gradient(180deg,rgb(255_255_255/0.55),transparent)]" />

      <div className="relative mx-auto max-w-6xl px-4 pb-24 pt-6 sm:px-6 lg:px-8">
        <header className="mb-10 flex flex-wrap items-end justify-between gap-6">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
          >
            <p className="mb-2 text-[11px] font-semibold tracking-[0.28em] text-sky-deep uppercase">
              Personal trading log
            </p>
            <h1 className="font-display text-5xl leading-none tracking-tight text-ink sm:text-6xl">
              DAYBOOK
            </h1>
            <p className="mt-3 max-w-md text-base text-ink/60">
              Log the session. Tag the emotion. Keep the edge.
            </p>
          </motion.div>

          <motion.div
            className="flex flex-wrap items-center gap-3"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12, duration: 0.45 }}
          >
            <button
              type="button"
              onClick={handleReset}
              className="rounded-full border border-line px-4 py-2 text-sm text-ink/55 transition hover:border-ink/25 hover:text-ink"
            >
              Reset demo
            </button>
            <button
              type="button"
              onClick={() => openNew()}
              className="rounded-full bg-ink px-5 py-2.5 text-sm font-semibold text-mist shadow-[0_12px_30px_rgb(11_18_32/0.22)] transition hover:-translate-y-0.5 hover:bg-ink-soft"
            >
              Log trade
            </button>
          </motion.div>
        </header>

        <motion.section
          className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.08, duration: 0.5 }}
        >
          <Stat
            label="Net P&L"
            value={formatMoney(stats.netPnl)}
            tone={pnlTone(stats.netPnl)}
            hint={format(month, 'MMMM')}
          />
          <Stat
            label="Win rate"
            value={`${Math.round(stats.winRate * 100)}%`}
            tone="flat"
            hint={`${stats.wins}W / ${stats.losses}L`}
          />
          <Stat
            label="Profit factor"
            value={
              stats.profitFactor === Infinity
                ? '∞'
                : stats.profitFactor
                  ? stats.profitFactor.toFixed(2)
                  : '—'
            }
            tone="flat"
            hint={`Expectancy ${formatMoney(stats.expectancy)}`}
          />
          <Stat
            label="Trades"
            value={String(stats.tradeCount)}
            tone="flat"
            hint={`Best ${formatCompact(stats.bestDay)} · Worst ${formatCompact(stats.worstDay)}`}
          />
        </motion.section>

        <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.16, duration: 0.55 }}
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <h2 className="font-display text-2xl tracking-tight">Session calendar</h2>
              <div className="flex items-center gap-2">
                <NavBtn onClick={() => setMonth((m) => subMonths(m, 1))} label="Prev" />
                <span className="min-w-36 text-center text-sm font-medium text-ink/70">
                  {grid.label}
                </span>
                <NavBtn onClick={() => setMonth((m) => addMonths(m, 1))} label="Next" />
              </div>
            </div>

            <div className="rounded-[28px] border border-line bg-white/55 p-4 shadow-[0_20px_60px_rgb(61_111_148/0.08)] backdrop-blur-md sm:p-5">
              <div className="mb-2 grid grid-cols-7 gap-1.5 text-center text-[11px] font-semibold tracking-wide text-ink/40 uppercase">
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d) => (
                  <div key={d} className="py-1">
                    {d}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-1.5">
                {Array.from({ length: grid.lead }).map((_, i) => (
                  <div key={`lead-${i}`} className="aspect-square rounded-2xl" />
                ))}
                {grid.days.map((day) => {
                  const key = format(day, 'yyyy-MM-dd')
                  const pnl = dayMap[key]
                  const selected = key === selectedDay
                  const tone = pnl === undefined ? 'empty' : pnlTone(pnl)
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setSelectedDay(key)}
                      className={[
                        'aspect-square rounded-2xl border p-1.5 text-left transition duration-200',
                        selected
                          ? 'border-ink bg-ink text-mist shadow-lg shadow-ink/20'
                          : 'border-transparent hover:border-line hover:bg-white/80',
                        !selected && tone === 'up' ? 'bg-profit-soft/70' : '',
                        !selected && tone === 'down' ? 'bg-loss-soft/70' : '',
                        !selected && tone === 'empty' ? 'bg-white/35' : '',
                      ].join(' ')}
                    >
                      <div
                        className={[
                          'text-[11px] font-semibold',
                          selected ? 'text-mist/70' : 'text-ink/45',
                        ].join(' ')}
                      >
                        {format(day, 'd')}
                      </div>
                      {pnl !== undefined && (
                        <div
                          className={[
                            'mt-1 text-[10px] font-semibold sm:text-[11px]',
                            selected
                              ? 'text-mist'
                              : tone === 'up'
                                ? 'tone-up'
                                : tone === 'down'
                                  ? 'tone-down'
                                  : 'tone-flat',
                          ].join(' ')}
                        >
                          {formatCompact(pnl)}
                        </div>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>

            <div className="mt-8">
              <div className="mb-4 flex items-end justify-between gap-3">
                <div>
                  <h2 className="font-display text-2xl tracking-tight">Recent trades</h2>
                  <p className="text-sm text-ink/50">Latest entries across the book</p>
                </div>
              </div>
              <TradeRows trades={allSorted} onEdit={openEdit} onDelete={deleteTrade} />
            </div>
          </motion.section>

          <motion.aside
            className="space-y-6"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.22, duration: 0.55 }}
          >
            <div className="rounded-[28px] border border-line bg-ink p-5 text-mist shadow-[0_24px_50px_rgb(11_18_32/0.25)] sm:p-6">
              <div className="mb-1 text-[11px] font-semibold tracking-[0.22em] text-sky/70 uppercase">
                Selected session
              </div>
              <div className="font-display text-3xl tracking-tight">
                {format(new Date(`${selectedDay}T12:00:00`), 'EEE, MMM d')}
              </div>
              <div className={`mt-2 text-2xl font-semibold ${pnlTone(dayPnl) === 'up' ? 'text-profit' : pnlTone(dayPnl) === 'down' ? 'text-[#f0a398]' : 'text-mist/50'}`}>
                {dayTrades.length ? formatMoney(dayPnl) : 'No trades'}
              </div>

              <div className="mt-5 space-y-3">
                {dayTrades.length === 0 && (
                  <p className="text-sm text-mist/55">
                    Empty day. Log a trade or write a reflection while the session is fresh.
                  </p>
                )}
                {dayTrades.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => openEdit(t)}
                    className="flex w-full items-start justify-between gap-3 rounded-2xl border border-white/10 bg-white/5 px-3.5 py-3 text-left transition hover:bg-white/10"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold">{t.symbol}</span>
                        <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-mist/70">
                          {t.side}
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-mist/50">
                        {t.setup || 'No setup tag'} · {emotionLabel(t.emotion)}
                      </div>
                    </div>
                    <div className={`text-sm font-semibold ${t.pnl >= 0 ? 'text-profit' : 'text-[#f0a398]'}`}>
                      {formatMoney(t.pnl)}
                    </div>
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={() => openNew(selectedDay)}
                className="mt-5 w-full rounded-full bg-mist py-2.5 text-sm font-semibold text-ink transition hover:bg-white"
              >
                Add trade for this day
              </button>
            </div>

            <div className="rounded-[28px] border border-line bg-white/60 p-5 backdrop-blur-md sm:p-6">
              <h3 className="font-display text-xl tracking-tight">Evening reflection</h3>
              <p className="mt-1 text-sm text-ink/50">How did the session feel?</p>

              <div className="mt-4 flex gap-2">
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setMood(n)}
                    className={[
                      'h-9 w-9 rounded-full text-sm font-semibold transition',
                      mood === n
                        ? 'bg-ink text-mist'
                        : 'border border-line text-ink/45 hover:border-ink/30',
                    ].join(' ')}
                  >
                    {n}
                  </button>
                ))}
              </div>

              <textarea
                value={reflectionText}
                onChange={(e) => setReflectionText(e.target.value)}
                rows={4}
                placeholder="What did you do well? What rule did you bend?"
                className="mt-4 w-full resize-none rounded-2xl border border-line bg-white/80 px-3.5 py-3 text-sm outline-none transition focus:border-sky-deep/40"
              />
              <button
                type="button"
                onClick={saveReflection}
                className="mt-3 rounded-full border border-line px-4 py-2 text-sm font-medium transition hover:border-ink/25"
              >
                Save reflection
              </button>
            </div>

            <EmotionLegend trades={monthTrades} />
          </motion.aside>
        </div>
      </div>

      <AnimatePresence>
        {formOpen && (
          <TradeForm
            draft={draft}
            setDraft={setDraft}
            editing={Boolean(editingId)}
            onClose={() => setFormOpen(false)}
            onSave={saveTrade}
            onDelete={editingId ? () => deleteTrade(editingId) : undefined}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function Stat({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string
  hint: string
  tone: 'up' | 'down' | 'flat'
}) {
  return (
    <div className="rounded-[24px] border border-line bg-white/55 px-4 py-4 backdrop-blur-md">
      <div className="text-[11px] font-semibold tracking-[0.18em] text-ink/40 uppercase">
        {label}
      </div>
      <div className={`mt-2 font-display text-3xl tracking-tight ${tone === 'up' ? 'tone-up' : tone === 'down' ? 'tone-down' : ''}`}>
        {value}
      </div>
      <div className="mt-1 text-xs text-ink/45">{hint}</div>
    </div>
  )
}

function NavBtn({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="grid h-8 w-8 place-items-center rounded-full border border-line text-ink/60 transition hover:border-ink/30 hover:text-ink"
    >
      {label === 'Prev' ? '‹' : '›'}
    </button>
  )
}

function TradeRows({
  trades,
  onEdit,
  onDelete,
}: {
  trades: Trade[]
  onEdit: (t: Trade) => void
  onDelete: (id: string) => void
}) {
  if (!trades.length) {
    return (
      <div className="rounded-[24px] border border-dashed border-line px-5 py-10 text-center text-sm text-ink/45">
        No trades yet. Log your first session.
      </div>
    )
  }

  return (
    <div className="overflow-hidden rounded-[24px] border border-line bg-white/55 backdrop-blur-md">
      {trades.map((t, i) => (
        <div
          key={t.id}
          className={[
            'flex flex-wrap items-center gap-3 px-4 py-3.5 sm:px-5',
            i !== trades.length - 1 ? 'border-b border-line' : '',
          ].join(' ')}
        >
          <button
            type="button"
            onClick={() => onEdit(t)}
            className="flex min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1 text-left"
          >
            <div className="w-16 shrink-0 text-xs font-medium text-ink/45">
              {format(new Date(`${t.date}T12:00:00`), 'MMM d')}
            </div>
            <div className="w-16 font-semibold">{t.symbol}</div>
            <div className="rounded-full bg-ink/5 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-ink/55 uppercase">
              {t.side}
            </div>
            <div className="text-sm text-ink/55">{t.setup || '—'}</div>
            <div className="rounded-full border border-line px-2 py-0.5 text-[11px] text-ink/55">
              {emotionLabel(t.emotion)}
            </div>
          </button>
          <div className={`ml-auto font-semibold ${t.pnl >= 0 ? 'tone-up' : 'tone-down'}`}>
            {formatMoney(t.pnl)}
          </div>
          <button
            type="button"
            aria-label="Delete trade"
            onClick={() => onDelete(t.id)}
            className="text-ink/30 transition hover:text-loss"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}

function EmotionLegend({ trades }: { trades: Trade[] }) {
  const counts = EMOTIONS.map((e) => ({
    emotion: e,
    count: trades.filter((t) => t.emotion === e).length,
    pnl: trades.filter((t) => t.emotion === e).reduce((s, t) => s + t.pnl, 0),
  })).filter((x) => x.count > 0)

  return (
    <div className="rounded-[28px] border border-line bg-white/55 p-5 backdrop-blur-md sm:p-6">
      <h3 className="font-display text-xl tracking-tight">Mind by emotion</h3>
      <p className="mt-1 text-sm text-ink/50">How psychology mapped to P&L this month</p>
      <div className="mt-4 space-y-2.5">
        {counts.length === 0 && (
          <p className="text-sm text-ink/45">No tagged trades yet.</p>
        )}
        {counts.map((c) => (
          <div key={c.emotion} className="flex items-center justify-between gap-3 text-sm">
            <div className="flex items-center gap-2">
              <span className="font-medium">{emotionLabel(c.emotion)}</span>
              <span className="text-ink/40">×{c.count}</span>
            </div>
            <span className={c.pnl >= 0 ? 'tone-up font-semibold' : 'tone-down font-semibold'}>
              {formatMoney(c.pnl)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function TradeForm({
  draft,
  setDraft,
  editing,
  onClose,
  onSave,
  onDelete,
}: {
  draft: Draft
  setDraft: (d: Draft) => void
  editing: boolean
  onClose: () => void
  onSave: () => void
  onDelete?: () => void
}) {
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
        aria-label={editing ? 'Edit trade' : 'Log trade'}
        className="max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-[28px] bg-cloud p-5 shadow-2xl sm:p-6"
        initial={{ opacity: 0, y: 28, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 18, scale: 0.98 }}
        transition={{ type: 'spring', stiffness: 320, damping: 28 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <h2 className="font-display text-2xl tracking-tight">
              {editing ? 'Edit trade' : 'Log trade'}
            </h2>
            <p className="text-sm text-ink/50">Fast entry — emotion included.</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-9 w-9 place-items-center rounded-full border border-line text-ink/50"
          >
            ×
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Date">
            <input
              type="date"
              value={draft.date}
              onChange={(e) => setDraft({ ...draft, date: e.target.value })}
              className="field"
            />
          </Field>
          <Field label="Symbol">
            <input
              value={draft.symbol}
              onChange={(e) => setDraft({ ...draft, symbol: e.target.value })}
              placeholder="NQ"
              className="field"
            />
          </Field>
          <Field label="Side">
            <div className="flex gap-2">
              {(['long', 'short'] as Side[]).map((side) => (
                <button
                  key={side}
                  type="button"
                  onClick={() => setDraft({ ...draft, side })}
                  className={[
                    'flex-1 rounded-xl py-2 text-sm font-semibold capitalize',
                    draft.side === side
                      ? side === 'long'
                        ? 'bg-profit text-white'
                        : 'bg-loss text-white'
                      : 'border border-line text-ink/55',
                  ].join(' ')}
                >
                  {side}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Emotion">
            <select
              value={draft.emotion}
              onChange={(e) => setDraft({ ...draft, emotion: e.target.value as Emotion })}
              className="field"
            >
              {EMOTIONS.map((e) => (
                <option key={e} value={e}>
                  {emotionLabel(e)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Entry">
            <input
              type="number"
              value={draft.entry}
              onChange={(e) => setDraft({ ...draft, entry: e.target.value })}
              className="field"
            />
          </Field>
          <Field label="Exit">
            <input
              type="number"
              value={draft.exit}
              onChange={(e) => setDraft({ ...draft, exit: e.target.value })}
              className="field"
            />
          </Field>
          <Field label="Size">
            <input
              type="number"
              value={draft.size}
              onChange={(e) => setDraft({ ...draft, size: e.target.value })}
              className="field"
            />
          </Field>
          <Field label="P&L ($)">
            <input
              type="number"
              value={draft.pnl}
              onChange={(e) => setDraft({ ...draft, pnl: e.target.value })}
              placeholder="2400 or -450"
              className="field"
            />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Setup">
              <input
                value={draft.setup}
                onChange={(e) => setDraft({ ...draft, setup: e.target.value })}
                placeholder="ORB continuation"
                className="field"
              />
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="Notes">
              <textarea
                value={draft.notes}
                onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
                rows={3}
                placeholder="What was the plan? Did you follow it?"
                className="field resize-none"
              />
            </Field>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onSave}
            className="rounded-full bg-ink px-5 py-2.5 text-sm font-semibold text-mist"
          >
            {editing ? 'Save changes' : 'Add to daybook'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-line px-4 py-2.5 text-sm"
          >
            Cancel
          </button>
          {onDelete && (
            <button
              type="button"
              onClick={onDelete}
              className="ml-auto rounded-full px-4 py-2.5 text-sm text-loss"
            >
              Delete
            </button>
          )}
        </div>
      </motion.div>
      <style>{`
        .field {
          width: 100%;
          border-radius: 0.9rem;
          border: 1px solid var(--color-line);
          background: white;
          padding: 0.6rem 0.8rem;
          outline: none;
        }
        .field:focus {
          border-color: rgb(61 111 148 / 0.45);
        }
      `}</style>
    </motion.div>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block text-xs font-semibold tracking-wide text-ink/45 uppercase">
      <span className="mb-1.5 block">{label}</span>
      {children}
    </label>
  )
}
