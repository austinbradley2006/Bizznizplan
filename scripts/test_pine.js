#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

require("../web/js/engine.js");
require("../web/js/pine.js");

const scripts = {
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

function run(name, pine, bars, extra) {
  const broker = global.NQEngine.createBroker(bars, Object.assign({
    pointValue: 20,
    tickSize: 0.25,
    commission: 2.25,
    slippageTicks: 1,
    qty: 1,
    initialCapital: 100000,
    barsPerYear: 252,
  }, extra || {}));
  const out = global.NQPine.runPine(pine, bars, { broker });
  const r = out.result;
  if (r.trades < 1) throw new Error(name + " expected trades");
  console.log(name, "trades=" + r.trades, "net=" + Math.round(r.netProfit), "pf=" + r.profitFactor.toFixed(2));
  return out;
}

const daily = JSON.parse(fs.readFileSync(path.join(__dirname, "../web/data/nq_1d.json"), "utf8"));
console.log(global.NQPine.transpile(scripts.sma));
for (const [name, pine] of Object.entries(scripts)) {
  run("1d:" + name, pine, daily.bars);
}
const hourly = JSON.parse(fs.readFileSync(path.join(__dirname, "../web/data/nq_1h.json"), "utf8"));
run("1h:sma", scripts.sma, hourly.bars, { barsPerYear: 252 * 23 });
console.log("ok");
