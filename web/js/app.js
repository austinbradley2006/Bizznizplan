const EXAMPLES = {
  sma: `//@version=5
strategy("NQ SMA Cross", overlay=true, initial_capital=100000, default_qty_value=1, pyramiding=0)

fastLen = input.int(10, "Fast SMA")
slowLen = input.int(50, "Slow SMA")

fast = ta.sma(close, fastLen)
slow = ta.sma(close, slowLen)

plot(fast, "Fast", color=color.aqua)
plot(slow, "Slow", color=color.orange)

if ta.crossover(fast, slow)
    strategy.entry("Long", strategy.long)
if ta.crossunder(fast, slow)
    strategy.entry("Short", strategy.short)
`,
  rsi: `//@version=5
strategy("NQ RSI Flip", overlay=true, initial_capital=100000, default_qty_value=1, pyramiding=0)

len = input.int(14, "RSI Length")
os = input.int(30, "Oversold")
ob = input.int(70, "Overbought")

r = ta.rsi(close, len)

if ta.crossover(r, os)
    strategy.entry("Long", strategy.long)
if ta.crossunder(r, ob)
    strategy.entry("Short", strategy.short)
`,
  donchian: `//@version=5
strategy("NQ Donchian Breakout", overlay=true, initial_capital=100000, default_qty_value=1, pyramiding=0)

n = input.int(20, "Channel Length")

upper = ta.highest(high, n)
lower = ta.lowest(low, n)

plot(upper, "Upper", color=color.red)
plot(lower, "Lower", color=color.green)

if close > upper[1]
    strategy.entry("Long", strategy.long)
if close < lower[1]
    strategy.entry("Short", strategy.short)
`,
  ema: `//@version=5
strategy("NQ EMA Trend", overlay=true, initial_capital=100000, default_qty_value=1, pyramiding=0)

len = input.int(21, "EMA Length")
atrLen = input.int(14, "ATR Length")
band = input.float(0.25, "ATR Filter")

e = ta.ema(close, len)
a = ta.atr(atrLen)

plot(e, "EMA", color=color.blue)

if close > e + a * band
    strategy.entry("Long", strategy.long)
if close < e - a * band
    strategy.entry("Short", strategy.short)
`,
};

const CONTRACTS = {
  NQ: { label: "NQ ($20/pt)", pointValue: 20, tickSize: 0.25, commission: 2.25, slippageTicks: 1 },
  MNQ: { label: "MNQ ($2/pt)", pointValue: 2, tickSize: 0.25, commission: 0.52, slippageTicks: 1 },
};

const INTERVALS = {
  "1d": { file: "data/nq_1d.json", label: "1D · 365 days", timeVisible: false },
  "1h": { file: "data/nq_1h.json", label: "1H · 365 days", timeVisible: true },
  "15m": { file: "data/nq_15m.json", label: "15m · 60 days", timeVisible: true },
};

const state = {
  bars: [],
  meta: null,
  chart: null,
  candles: null,
  plots: [],
  equityChart: null,
  equitySeries: null,
  inputValues: {},
};

function $(id) {
  return document.getElementById(id);
}

function usd(n, digits) {
  const d = digits == null ? (Math.abs(n) >= 100 ? 0 : 2) : digits;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });
}

function fmtNum(n, d) {
  if (n == null || Number.isNaN(n)) return "—";
  if (!Number.isFinite(n)) return "∞";
  return n.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

function candleData(bars) {
  return bars.map((b) => ({
    time: b.time,
    open: b.open,
    high: b.high,
    low: b.low,
    close: b.close,
  }));
}

function initCharts() {
  const chartEl = $("chart");
  const eqEl = $("equity");
  const opts = {
    layout: {
      background: { color: "#131722" },
      textColor: "#d1d4dc",
      fontFamily: "Trebuchet MS, sans-serif",
    },
    grid: {
      vertLines: { color: "#1e222d" },
      horzLines: { color: "#1e222d" },
    },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#2a2e39" },
    timeScale: { borderColor: "#2a2e39", secondsVisible: false },
    handleScroll: { mouseWheel: true, pressedMouseMove: true },
    handleScale: { mouseWheel: true, pinch: true },
  };
  state.chart = LightweightCharts.createChart(chartEl, opts);
  state.candles = state.chart.addCandlestickSeries({
    upColor: "#26a69a",
    downColor: "#ef5350",
    wickUpColor: "#26a69a",
    wickDownColor: "#ef5350",
    borderVisible: false,
  });
  state.equityChart = LightweightCharts.createChart(eqEl, {
    ...opts,
    layout: { ...opts.layout, textColor: "#868993" },
    timeScale: { ...opts.timeScale, visible: false },
    rightPriceScale: { borderColor: "#2a2e39", scaleMargins: { top: 0.15, bottom: 0.1 } },
  });
  state.equitySeries = state.equityChart.addAreaSeries({
    lineColor: "#2962ff",
    topColor: "rgba(41, 98, 255, 0.28)",
    bottomColor: "rgba(41, 98, 255, 0.02)",
    lineWidth: 2,
    priceLineVisible: false,
  });
  const ro = new ResizeObserver(() => {
    state.chart.applyOptions({ width: chartEl.clientWidth, height: chartEl.clientHeight });
    state.equityChart.applyOptions({ width: eqEl.clientWidth, height: eqEl.clientHeight });
  });
  ro.observe(chartEl);
  ro.observe(eqEl);
  state.chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
    if (!range) return;
    state.equityChart.timeScale().setVisibleLogicalRange(range);
  });
}

async function loadInterval(key) {
  const spec = INTERVALS[key];
  const res = await fetch(spec.file);
  if (!res.ok) throw new Error("Could not load " + spec.file);
  const payload = await res.json();
  state.meta = payload;
  state.bars = payload.bars;
  state.chart.applyOptions({
    timeScale: { timeVisible: spec.timeVisible, secondsVisible: false, borderColor: "#2a2e39" },
  });
  state.candles.setData(candleData(state.bars));
  $("symbolMeta").textContent =
    payload.symbol +
    " · " +
    payload.exchange +
    " · " +
    state.bars.length.toLocaleString() +
    " bars · " +
    spec.label;
  state.chart.timeScale().fitContent();
}

function renderInputs(pine) {
  const defs = NQPine.extractInputs(pine);
  const box = $("inputs");
  box.innerHTML = "";
  const next = {};
  for (const def of defs) {
    const prev = state.inputValues[def.name];
    const value = prev != null ? prev : def.value;
    next[def.name] = value;
    next[def.title] = value;
    const wrap = document.createElement("label");
    wrap.className = "input-row";
    wrap.innerHTML =
      "<span>" +
      def.title +
      '</span><input type="' +
      (def.type === "bool" ? "checkbox" : "number") +
      '" data-name="' +
      def.name +
      '" data-title="' +
      def.title +
      '" data-type="' +
      def.type +
      '" />';
    const el = wrap.querySelector("input");
    if (def.type === "bool") el.checked = Boolean(value);
    else {
      el.value = value;
      el.step = def.type === "float" ? "0.01" : "1";
      if (def.minval != null) el.min = def.minval;
      if (def.maxval != null) el.max = def.maxval;
    }
    el.addEventListener("change", () => {
      const v = def.type === "bool" ? el.checked : def.type === "float" ? parseFloat(el.value) : parseInt(el.value, 10);
      state.inputValues[def.name] = v;
      state.inputValues[def.title] = v;
      runStrategy();
    });
    box.appendChild(wrap);
  }
  if (!defs.length) {
    box.innerHTML = '<div class="input-empty">No inputs in this script</div>';
  }
  defs.forEach((d, i) => {
    next["in" + i] = next[d.name];
  });
  state.inputValues = next;
}

function clearPlots() {
  for (const s of state.plots) {
    try {
      state.chart.removeSeries(s);
    } catch (_e) {}
  }
  state.plots = [];
  state.candles.setMarkers([]);
}

function runStrategy() {
  const pine = $("pine").value;
  const key = $("contract").value;
  const contract = Object.assign(
    { initialCapital: 100000, qty: 1, barsPerYear: $("interval").value === "1d" ? 252 : $("interval").value === "1h" ? 252 * 23 : 252 * 23 * 4 },
    CONTRACTS[key]
  );
  $("status").textContent = "Running…";
  $("status").className = "status";
  try {
    renderInputs(pine);
    const broker = NQEngine.createBroker(state.bars, contract);
    const out = NQPine.runPine(pine, state.bars, { broker, inputs: state.inputValues });
    paintResult(out);
    $("status").textContent = out.strategyConfig.name + " · " + out.result.trades + " trades";
  } catch (err) {
    console.error(err);
    $("status").textContent = (err && err.message) || String(err);
    $("status").className = "status error";
    if (err && err.compiled) console.log(err.compiled);
  }
}

function paintResult(out) {
  clearPlots();
  const r = out.result;
  for (const p of out.plots) {
    const series = state.chart.addLineSeries({
      color: typeof p.color === "string" ? p.color : "#2962ff",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: p.title,
    });
    const data = [];
    for (let i = 0; i < state.bars.length; i += 1) {
      const v = p.values[i];
      if (v == null || Number.isNaN(v) || !Number.isFinite(v)) continue;
      data.push({ time: state.bars[i].time, value: v });
    }
    series.setData(data);
    state.plots.push(series);
  }
  const markers = [];
  for (const t of r.tradeList) {
    markers.push({
      time: t.entryTime,
      position: t.side === "Long" ? "belowBar" : "aboveBar",
      color: t.side === "Long" ? "#26a69a" : "#ef5350",
      shape: t.side === "Long" ? "arrowUp" : "arrowDown",
      text: t.side === "Long" ? "L" : "S",
    });
    markers.push({
      time: t.exitTime,
      position: t.side === "Long" ? "aboveBar" : "belowBar",
      color: "#868993",
      shape: "circle",
      text: t.pnl >= 0 ? "+" : "−",
    });
  }
  markers.sort((a, b) => {
    if (a.time < b.time) return -1;
    if (a.time > b.time) return 1;
    return 0;
  });
  state.candles.setMarkers(markers);
  state.equitySeries.setData(r.equityCurve.map((p) => ({ time: p.time, value: p.value })));
  state.equityChart.timeScale().fitContent();

  const up = r.netProfit >= 0;
  $("metrics").innerHTML = [
    metric("Net profit", usd(r.netProfit, 0), up),
    metric("Return", fmtNum(r.netProfitPct, 1) + "%", up),
    metric("Trades", String(r.trades)),
    metric("Win rate", fmtNum(r.winRate, 1) + "%"),
    metric("Profit factor", fmtNum(r.profitFactor, 2)),
    metric("Max DD", usd(-Math.abs(r.maxDrawdown), 0), false),
    metric("Avg trade", usd(r.avgTrade, 0), r.avgTrade >= 0),
    metric("Sharpe", r.sharpe == null ? "—" : fmtNum(r.sharpe, 2)),
  ].join("");

  $("openPos").textContent = r.openPosition
    ? (r.openPosition > 0 ? "Long " : "Short ") +
      Math.abs(r.openPosition) +
      " @ " +
      fmtNum(r.openAvg, 2) +
      " · " +
      usd(r.openPnl, 0)
    : "Flat";

  const body = $("tradesBody");
  body.innerHTML = r.tradeList
    .slice()
    .reverse()
    .map(
      (t) =>
        "<tr class=\"" +
        (t.pnl >= 0 ? "win" : "loss") +
        "\"><td>" +
        t.side +
        "</td><td>" +
        fmtTime(t.entryTime) +
        "</td><td>" +
        fmtTime(t.exitTime) +
        "</td><td>" +
        fmtNum(t.entry, 2) +
        "</td><td>" +
        fmtNum(t.exit, 2) +
        "</td><td>" +
        fmtNum(t.points, 2) +
        "</td><td>" +
        usd(t.pnl, 0) +
        "</td></tr>"
    )
    .join("");
}

function metric(label, value, up) {
  const cls = up == null ? "" : up ? " up" : " down";
  return '<div class="metric' + cls + '"><div class="mlabel">' + label + '</div><div class="mvalue">' + value + "</div></div>";
}

function fmtTime(t) {
  if (typeof t === "number") {
    const d = new Date(t * 1000);
    return d.toISOString().replace("T", " ").slice(0, 16);
  }
  return String(t);
}

async function main() {
  initCharts();
  $("pine").value = EXAMPLES.sma;
  $("examples").addEventListener("change", () => {
    $("pine").value = EXAMPLES[$("examples").value];
    state.inputValues = {};
    runStrategy();
  });
  $("run").addEventListener("click", runStrategy);
  $("interval").addEventListener("change", async () => {
    $("status").textContent = "Loading NQ…";
    await loadInterval($("interval").value);
    runStrategy();
  });
  $("contract").addEventListener("change", runStrategy);
  $("pine").addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      runStrategy();
    }
  });
  await loadInterval("1d");
  runStrategy();
}

main().catch((err) => {
  $("status").textContent = err.message;
  $("status").className = "status error";
});
