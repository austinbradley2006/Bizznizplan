(function (global) {
  "use strict";

  function roundTick(price, tick) {
    return Math.round(price / tick) * tick;
  }

  function createBroker(bars, contract) {
    const tick = contract.tickSize || 0.25;
    const pointValue = contract.pointValue || 20;
    const slippageTicks = contract.slippageTicks == null ? 1 : contract.slippageTicks;
    const commission = contract.commission == null ? 2.5 : contract.commission;
    const defaultQty = contract.qty || 1;

    const state = {
      position: 0,
      avgPrice: 0,
      entryId: null,
      entryBar: null,
      entryTime: null,
      realized: 0,
      pending: [],
      protective: null,
      trades: [],
      equity: [],
      initialCapital: contract.initialCapital || 100000,
      cfg: {},
    };

    function slip(price, signedQty) {
      const raw = price + Math.sign(signedQty) * slippageTicks * tick;
      return roundTick(raw, tick);
    }

    function mtm(i) {
      if (!state.position) return 0;
      const px = bars[i].close;
      return (px - state.avgPrice) * state.position * pointValue;
    }

    function fill(signedQty, price, i, id, kind) {
      if (!signedQty) return;
      const fillPrice = slip(price, signedQty);
      const fee = commission * Math.abs(signedQty);
      if (state.position === 0 || Math.sign(state.position) === Math.sign(signedQty)) {
        const newQty = state.position + signedQty;
        if (state.position === 0) {
          state.avgPrice = fillPrice;
          state.entryId = id;
          state.entryBar = i;
          state.entryTime = bars[i].time;
        } else {
          state.avgPrice =
            (state.avgPrice * Math.abs(state.position) + fillPrice * Math.abs(signedQty)) /
            Math.abs(newQty);
        }
        state.position = newQty;
        state.realized -= fee;
        return;
      }
      const closeQty = Math.min(Math.abs(state.position), Math.abs(signedQty)) * Math.sign(state.position);
      const exitPrice = fillPrice;
      const pts = (exitPrice - state.avgPrice) * Math.sign(state.position);
      const pnl = pts * pointValue * Math.abs(closeQty) - fee;
      state.realized += pnl;
      state.trades.push({
        id: state.entryId || id,
        side: state.position > 0 ? "Long" : "Short",
        qty: Math.abs(closeQty),
        entry: state.avgPrice,
        exit: exitPrice,
        entryTime: state.entryTime,
        exitTime: bars[i].time,
        entryBar: state.entryBar,
        exitBar: i,
        points: pts,
        pnl,
        kind: kind || "signal",
      });
      state.position -= closeQty;
      const leftover = signedQty + closeQty;
      if (state.position === 0) {
        state.avgPrice = 0;
        state.entryId = null;
        state.entryBar = null;
        state.entryTime = null;
        state.protective = null;
      }
      if (leftover) fill(leftover, price, i, id, kind);
    }

    function processPending(i, price) {
      const orders = state.pending;
      state.pending = [];
      for (const o of orders) {
        if (o.type === "close") {
          if (state.position) fill(-state.position, price, i, o.id, "close");
        } else if (o.type === "entry" || o.type === "reverse") {
          if (state.cfg.pyramiding === 0 && state.position && Math.sign(state.position) === Math.sign(o.qty)) {
            continue;
          }
          if (state.position && Math.sign(state.position) !== Math.sign(o.qty)) {
            fill(-state.position, price, i, o.id, "reverse");
          }
          fill(o.qty, price, i, o.id, o.type);
        }
      }
    }

    function checkProtective(i) {
      const prot = state.protective;
      if (!prot || !state.position) return;
      const bar = bars[i];
      const dir = Math.sign(state.position);
      let stop = prot.stop;
      let limit = prot.limit;
      if (prot.loss != null) stop = state.avgPrice - dir * prot.loss * tick;
      if (prot.profit != null) limit = state.avgPrice + dir * prot.profit * tick;
      let hitStop = false;
      let hitLimit = false;
      if (stop != null) {
        hitStop = dir > 0 ? bar.low <= stop : bar.high >= stop;
      }
      if (limit != null) {
        hitLimit = dir > 0 ? bar.high >= limit : bar.low <= limit;
      }
      if (hitStop && hitLimit) {
        fill(-state.position, stop, i, prot.id, "stop");
        return;
      }
      if (hitStop) fill(-state.position, stop, i, prot.id, "stop");
      else if (hitLimit) fill(-state.position, limit, i, prot.id, "target");
    }

    const broker = {
      get position() {
        return state.position;
      },
      get avgPrice() {
        return state.avgPrice;
      },
      get realized() {
        return state.realized;
      },
      get trades() {
        return state.trades;
      },
      configure(cfg) {
        state.cfg = cfg || {};
        if (state.cfg.initial_capital) state.initialCapital = Number(state.cfg.initial_capital);
        if (state.cfg.default_qty_value) contract.qty = Number(state.cfg.default_qty_value);
      },
      unrealized(i) {
        return mtm(i);
      },
      onBarOpen(i) {
        if (state.cfg.process_orders_on_close) return;
        if (i === 0) return;
        processPending(i, bars[i].open);
      },
      onBarClose(i) {
        checkProtective(i);
        if (state.cfg.process_orders_on_close) {
          processPending(i, bars[i].close);
        }
        const eq = state.initialCapital + state.realized + mtm(i);
        state.equity.push({ time: bars[i].time, value: eq });
      },
      entry(id, direction, qty, _i) {
        const q = Math.abs(Number(qty != null ? qty : contract.qty || defaultQty)) || 1;
        const signed = (direction >= 0 ? 1 : -1) * q;
        state.pending.push({ type: "entry", id, qty: signed });
      },
      close(id, _i) {
        state.pending.push({ type: "close", id });
      },
      exit(id, _from, opts) {
        state.protective = {
          id,
          profit: opts.profit,
          loss: opts.loss,
          stop: opts.stop,
          limit: opts.limit,
        };
      },
      finish(_last) {},
      summary() {
        const trades = state.trades;
        const wins = trades.filter((t) => t.pnl > 0);
        const losses = trades.filter((t) => t.pnl < 0);
        const grossWin = wins.reduce((s, t) => s + t.pnl, 0);
        const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));
        let peak = -Infinity;
        let maxDd = 0;
        let maxDdPct = 0;
        for (const p of state.equity) {
          if (p.value > peak) peak = p.value;
          const dd = peak - p.value;
          if (dd > maxDd) {
            maxDd = dd;
            maxDdPct = peak ? (dd / peak) * 100 : 0;
          }
        }
        const lastEq = state.equity.length
          ? state.equity[state.equity.length - 1].value
          : state.initialCapital;
        const rets = [];
        for (let i = 1; i < state.equity.length; i += 1) {
          const prev = state.equity[i - 1].value;
          if (prev) rets.push(state.equity[i].value / prev - 1);
        }
        let sharpe = null;
        if (rets.length > 2) {
          const mean = rets.reduce((s, x) => s + x, 0) / rets.length;
          const var_ =
            rets.reduce((s, x) => s + (x - mean) * (x - mean), 0) / (rets.length - 1);
          const std = Math.sqrt(var_);
          const perYear =
            contract.barsPerYear ||
            (typeof bars[0].time === "string" ? 252 : 252 * 23);
          sharpe = std ? (mean / std) * Math.sqrt(perYear) : 0;
        }
        return {
          name: state.cfg.name || "Strategy",
          netProfit: lastEq - state.initialCapital,
          netProfitPct: ((lastEq - state.initialCapital) / state.initialCapital) * 100,
          equity: lastEq,
          initialCapital: state.initialCapital,
          trades: trades.length,
          wins: wins.length,
          losses: losses.length,
          winRate: trades.length ? (wins.length / trades.length) * 100 : 0,
          profitFactor: grossLoss ? grossWin / grossLoss : grossWin ? Infinity : 0,
          avgTrade: trades.length ? trades.reduce((s, t) => s + t.pnl, 0) / trades.length : 0,
          avgWin: wins.length ? grossWin / wins.length : 0,
          avgLoss: losses.length ? -(grossLoss / losses.length) : 0,
          maxDrawdown: maxDd,
          maxDrawdownPct: maxDdPct,
          sharpe,
          openPosition: state.position,
          openAvg: state.avgPrice,
          openPnl: mtm(bars.length - 1),
          tradeList: trades,
          equityCurve: state.equity,
          pointValue,
        };
      },
    };

    return broker;
  }

  global.NQEngine = { createBroker };
})(typeof window !== "undefined" ? window : globalThis);
