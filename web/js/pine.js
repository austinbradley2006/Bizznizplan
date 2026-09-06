(function (global) {
  "use strict";

  function mapOutsideStrings(src, fn) {
    const parts = [];
    let i = 0;
    while (i < src.length) {
      const q = src[i];
      if (q === '"' || q === "'") {
        let j = i + 1;
        while (j < src.length) {
          if (src[j] === "\\") {
            j += 2;
            continue;
          }
          if (src[j] === q) {
            j += 1;
            break;
          }
          j += 1;
        }
        parts.push(src.slice(i, j));
        i = j;
        continue;
      }
      let j = i;
      while (j < src.length && src[j] !== '"' && src[j] !== "'") j += 1;
      parts.push(fn(src.slice(i, j)));
      i = j;
    }
    return parts.join("");
  }

  function splitArgs(argsStr) {
    const args = [];
    let cur = "";
    let depth = 0;
    let quote = null;
    for (let i = 0; i < argsStr.length; i += 1) {
      const ch = argsStr[i];
      if (quote) {
        cur += ch;
        if (ch === "\\" && i + 1 < argsStr.length) {
          cur += argsStr[i + 1];
          i += 1;
        } else if (ch === quote) quote = null;
        continue;
      }
      if (ch === '"' || ch === "'") {
        quote = ch;
        cur += ch;
        continue;
      }
      if (ch === "(" || ch === "[" || ch === "{") {
        depth += 1;
        cur += ch;
        continue;
      }
      if (ch === ")" || ch === "]" || ch === "}") {
        depth -= 1;
        cur += ch;
        continue;
      }
      if (ch === "," && depth === 0) {
        args.push(cur.trim());
        cur = "";
        continue;
      }
      cur += ch;
    }
    if (cur.trim()) args.push(cur.trim());
    return args;
  }

  function rewriteNamedArgs(argsStr) {
    const args = splitArgs(argsStr);
    if (!args.length) return argsStr;
    const pos = [];
    const kw = [];
    for (const arg of args) {
      const m = arg.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)([\s\S]*)$/);
      if (m) kw.push(`${m[1]}: ${m[2].trim()}`);
      else pos.push(arg);
    }
    if (!kw.length) return argsStr;
    pos.push("{ " + kw.join(", ") + " }");
    return pos.join(", ");
  }

  function transformCalls(src) {
    let out = "";
    let i = 0;
    while (i < src.length) {
      const ch = src[i];
      if (ch === '"' || ch === "'") {
        let j = i + 1;
        while (j < src.length) {
          if (src[j] === "\\") {
            j += 2;
            continue;
          }
          if (src[j] === ch) {
            j += 1;
            break;
          }
          j += 1;
        }
        out += src.slice(i, j);
        i = j;
        continue;
      }
      const m = src.slice(i).match(/^[A-Za-z_][A-Za-z0-9_.]*\s*\(/);
      if (m) {
        const raw = m[0];
        const name = raw.replace(/\s*\($/, "");
        const open = i + raw.length - 1;
        const close = matchingParen(src, open);
        if (close < 0) {
          out += src.slice(i);
          break;
        }
        const inner = src.slice(open + 1, close);
        if (name !== "if" && name !== "while" && name !== "for" && name !== "switch") {
          out += raw + transformCalls(rewriteNamedArgs(inner)) + ")";
        } else {
          out += raw + transformCalls(inner) + ")";
        }
        i = close + 1;
        continue;
      }
      out += ch;
      i += 1;
    }
    return out;
  }

  function matchingParen(s, open) {
    let depth = 0;
    let quote = null;
    for (let i = open; i < s.length; i += 1) {
      const ch = s[i];
      if (quote) {
        if (ch === "\\" ) {
          i += 1;
          continue;
        }
        if (ch === quote) quote = null;
        continue;
      }
      if (ch === '"' || ch === "'") {
        quote = ch;
        continue;
      }
      if (ch === "(") depth += 1;
      else if (ch === ")") {
        depth -= 1;
        if (depth === 0) return i;
      }
    }
    return -1;
  }

  function replaceKeywords(src) {
    return mapOutsideStrings(src, (chunk) => {
      let s = chunk.replace(/:=/g, "=");
      s = s.replace(/\band\b/g, "&&");
      s = s.replace(/\bor\b/g, "||");
      s = s.replace(/\bnot\b/g, "!");
      s = s.replace(/\bna\b(?!\s*\()/g, "NaN");
      return s;
    });
  }

  function lineIndent(line) {
    if (!line.trim()) return null;
    const m = line.match(/^[\t ]*/);
    const ws = m ? m[0] : "";
    return ws.replace(/\t/g, "    ").length;
  }

  function convertIfElse(line) {
    const ind = line.match(/^[\t ]*/)[0];
    const t = line.trim();
    if (t.startsWith("else if ")) {
      let rest = t.slice(8).trim();
      if (rest.endsWith("{")) rest = rest.slice(0, -1).trim();
      if (!rest.startsWith("(")) rest = "(" + rest + ")";
      return ind + "else if " + rest;
    }
    if (t === "else" || t === "else {") return ind + "else";
    if (t.startsWith("if ")) {
      let rest = t.slice(3).trim();
      if (rest.endsWith("{")) rest = rest.slice(0, -1).trim();
      if (!rest.startsWith("(")) rest = "(" + rest + ")";
      return ind + "if " + rest;
    }
    return line;
  }

  function indentToBraces(src) {
    const lines = src.replace(/\r\n/g, "\n").split("\n");
    const out = [];
    const stack = [0];
    const nextIndent = (from) => {
      for (let j = from; j < lines.length; j += 1) {
        const n = lineIndent(lines[j]);
        if (n !== null) return n;
      }
      return null;
    };
    for (let i = 0; i < lines.length; i += 1) {
      const raw = lines[i];
      const ind = lineIndent(raw);
      if (ind === null) {
        out.push("");
        continue;
      }
      while (ind < stack[stack.length - 1]) {
        stack.pop();
        out.push(" ".repeat(stack[stack.length - 1]) + "}");
      }
      let line = convertIfElse(raw);
      const nxt = nextIndent(i + 1);
      if (nxt !== null && nxt > ind) {
        line = line.replace(/\s*$/, "") + " {";
        stack.push(nxt);
      }
      out.push(line);
    }
    while (stack.length > 1) {
      stack.pop();
      out.push(" ".repeat(stack[stack.length - 1]) + "}");
    }
    return out.join("\n");
  }

  function stripComments(src) {
    return mapOutsideStrings(src, (chunk) =>
      chunk
        .replace(/\/\/@version=[^\n]*/g, "")
        .replace(/\/\/[^\n]*/g, "")
    );
  }

  function extractInputs(pine) {
    const inputs = [];
    const re = /([A-Za-z_][A-Za-z0-9_]*)\s*=\s*input\.(int|float|bool)\s*\(([\s\S]*?)\)/g;
    let m;
    while ((m = re.exec(pine))) {
      const name = m[1];
      const type = m[2];
      const args = splitArgs(transformCalls(rewriteNamedArgs(m[3])));
      let def = args[0];
      let title = name;
      let opts = {};
      for (let i = 1; i < args.length; i += 1) {
        const a = args[i].trim();
        if (a.startsWith("{")) {
          try {
            opts = Function('"use strict"; return (' + a + ")")();
          } catch (_e) {
            opts = {};
          }
        } else if (a.startsWith('"') || a.startsWith("'")) {
          title = a.slice(1, -1);
        }
      }
      if (opts.title) title = opts.title;
      let value;
      if (type === "bool") value = String(def).trim() === "true";
      else if (type === "float") value = parseFloat(def);
      else value = parseInt(def, 10);
      if (opts.minval != null && value < opts.minval) value = opts.minval;
      inputs.push({ name, type, title, value, minval: opts.minval, maxval: opts.maxval });
    }
    return inputs;
  }

  function transpile(pine) {
    let src = stripComments(pine);
    src = transformCalls(src);
    src = replaceKeywords(src);
    src = indentToBraces(src);
    return src;
  }

  function isFiniteNumber(n) {
    return typeof n === "number" && Number.isFinite(n);
  }

  function srcAt(src, offset) {
    if (src == null) return NaN;
    if (typeof src === "number" || typeof src === "boolean") {
      return offset === 0 ? Number(src) : NaN;
    }
    if (typeof src === "object") {
      try {
        const v = src[offset];
        if (v == null) return NaN;
        return Number(v);
      } catch (_e) {
        return NaN;
      }
    }
    const n = Number(src);
    return offset === 0 ? n : NaN;
  }

  function makeSeriesProxy(getter) {
    return new Proxy(
      {},
      {
        get(_t, prop) {
          if (prop === Symbol.toPrimitive || prop === "valueOf") {
            return () => getter(0);
          }
          if (prop === "toString") {
            return () => String(getter(0));
          }
          if (typeof prop === "string" && /^\d+$/.test(prop)) {
            return getter(parseInt(prop, 10));
          }
          return undefined;
        },
      }
    );
  }

  function createRuntime(bars, options) {
    const opts = options || {};
    const vars = Object.create(null);
    const initialized = Object.create(null);
    const plots = [];
    const inputValues = Object.assign({}, opts.inputs || {});
    let inputSeq = 0;
    const inputDefs = [];

    const rt = {
      i: 0,
      bars,
      vars,
      plots,
      strategyConfig: {
        name: "Strategy",
        overlay: true,
        initial_capital: 100000,
        default_qty_value: 1,
        pyramiding: 0,
        process_orders_on_close: false,
        commission_value: 0,
      },
      bar() {
        return bars[rt.i];
      },
      getVar(name, offset) {
        const arr = vars[name];
        if (!arr) return NaN;
        const idx = rt.i - offset;
        if (idx < 0 || idx >= arr.length) return NaN;
        const v = arr[idx];
        return v == null ? NaN : v;
      },
      setVar(name, value) {
        if (!vars[name]) vars[name] = [];
        const n = typeof value === "number" ? value : Number(value);
        vars[name][rt.i] = n;
        return n;
      },
    };

    function sma(src, len) {
      const n = Number(len);
      if (!n || n < 1) return NaN;
      let sum = 0;
      for (let k = 0; k < n; k += 1) {
        const v = srcAt(src, k);
        if (!isFiniteNumber(v)) return NaN;
        sum += v;
      }
      return sum / n;
    }

    function ema(src, len) {
      const n = Number(len);
      if (!n || n < 1) return NaN;
      const alpha = 2 / (n + 1);
      const key = "__ema_" + n + "_" + srcAt(src, 0);
      // Compute from history of source each bar (ok for N ~ 200).
      let prev = srcAt(src, n - 1);
      if (!isFiniteNumber(prev)) return NaN;
      for (let k = n - 2; k >= 0; k -= 1) {
        const v = srcAt(src, k);
        if (!isFiniteNumber(v)) return NaN;
        prev = alpha * v + (1 - alpha) * prev;
      }
      return prev;
    }

    function rsi(src, len) {
      const n = Number(len) || 14;
      let gains = 0;
      let losses = 0;
      for (let k = 0; k < n; k += 1) {
        const a = srcAt(src, k);
        const b = srcAt(src, k + 1);
        if (!isFiniteNumber(a) || !isFiniteNumber(b)) return NaN;
        const diff = a - b;
        if (diff >= 0) gains += diff;
        else losses -= diff;
      }
      if (losses === 0) return 100;
      const rs = gains / n / (losses / n);
      return 100 - 100 / (1 + rs);
    }

    function atr(len) {
      const n = Number(len) || 14;
      let sum = 0;
      for (let k = 0; k < n; k += 1) {
        const idx = rt.i - k;
        if (idx < 1) return NaN;
        const b = bars[idx];
        const prev = bars[idx - 1];
        const tr = Math.max(
          b.high - b.low,
          Math.abs(b.high - prev.close),
          Math.abs(b.low - prev.close)
        );
        sum += tr;
      }
      return sum / n;
    }

    function highest(src, len) {
      const n = Number(len);
      let m = -Infinity;
      for (let k = 0; k < n; k += 1) {
        const v = srcAt(src, k);
        if (!isFiniteNumber(v)) return NaN;
        if (v > m) m = v;
      }
      return m;
    }

    function lowest(src, len) {
      const n = Number(len);
      let m = Infinity;
      for (let k = 0; k < n; k += 1) {
        const v = srcAt(src, k);
        if (!isFiniteNumber(v)) return NaN;
        if (v < m) m = v;
      }
      return m;
    }

    function crossover(a, b) {
      const a0 = srcAt(a, 0);
      const a1 = srcAt(a, 1);
      const b0 = srcAt(b, 0);
      const b1 = srcAt(b, 1);
      if (![a0, a1, b0, b1].every(isFiniteNumber)) return false;
      return a1 <= b1 && a0 > b0;
    }

    function crossunder(a, b) {
      const a0 = srcAt(a, 0);
      const a1 = srcAt(a, 1);
      const b0 = srcAt(b, 0);
      const b1 = srcAt(b, 1);
      if (![a0, a1, b0, b1].every(isFiniteNumber)) return false;
      return a1 >= b1 && a0 < b0;
    }

    function change(src, len) {
      const n = Number(len) || 1;
      const a = srcAt(src, 0);
      const b = srcAt(src, n);
      if (!isFiniteNumber(a) || !isFiniteNumber(b)) return NaN;
      return a - b;
    }

    const ta = {
      sma,
      ema,
      rsi,
      atr,
      highest,
      lowest,
      crossover,
      crossunder,
      change,
      tr: function () {
        if (rt.i < 1) return bars[rt.i].high - bars[rt.i].low;
        const b = bars[rt.i];
        const p = bars[rt.i - 1];
        return Math.max(b.high - b.low, Math.abs(b.high - p.close), Math.abs(b.low - p.close));
      },
      vwma: function (src, len) {
        const n = Number(len);
        let pv = 0;
        let vv = 0;
        for (let k = 0; k < n; k += 1) {
          const idx = rt.i - k;
          if (idx < 0) return NaN;
          const v = srcAt(src, k);
          const vol = bars[idx].volume || 0;
          if (!isFiniteNumber(v)) return NaN;
          pv += v * vol;
          vv += vol;
        }
        return vv ? pv / vv : NaN;
      },
      stoch: function (src, highSrc, lowSrc, len) {
        const n = Number(len) || 14;
        const c = srcAt(src, 0);
        const h = highest(highSrc, n);
        const l = lowest(lowSrc, n);
        if (![c, h, l].every(isFiniteNumber) || h === l) return NaN;
        return 100 * ((c - l) / (h - l));
      },
    };

    const color = {
      red: "#ef5350",
      green: "#26a69a",
      blue: "#2962ff",
      orange: "#ff9800",
      yellow: "#ffeb3b",
      white: "#d1d4dc",
      gray: "#787b86",
      aqua: "#26c6da",
      teal: "#00897b",
      purple: "#ab47bc",
      black: "#000000",
      lime: "#00e676",
      fuchsia: "#e040fb",
      silver: "#9aa0aa",
      navy: "#1565c0",
      maroon: "#b71c1c",
      olive: "#827717",
      new: function (c) {
        return c;
      },
    };

    function parseInputArgs(def, titleOrOpts, opts) {
      let title;
      let extra = {};
      if (titleOrOpts && typeof titleOrOpts === "object" && !Array.isArray(titleOrOpts)) {
        extra = titleOrOpts;
        title = extra.title;
      } else if (typeof titleOrOpts === "string") {
        title = titleOrOpts;
        extra = opts && typeof opts === "object" ? opts : {};
      } else if (opts && typeof opts === "object") {
        extra = opts;
        title = extra.title;
      }
      return { def, title, extra };
    }

    function nextInput(type, def, titleOrOpts, opts) {
      const parsed = parseInputArgs(def, titleOrOpts, opts);
      const id = "in" + inputSeq;
      inputSeq += 1;
      if (inputDefs.length < inputSeq) {
        inputDefs.push({
          id,
          type,
          title: parsed.title || id,
          value: def,
        });
      }
      if (Object.prototype.hasOwnProperty.call(inputValues, id)) return inputValues[id];
      const byTitle = parsed.title && inputValues[parsed.title];
      if (byTitle != null) return byTitle;
      return def;
    }

    const input = {
      int: function (def, title, opts) {
        return Number(nextInput("int", def, title, opts));
      },
      float: function (def, title, opts) {
        return Number(nextInput("float", def, title, opts));
      },
      bool: function (def, title, opts) {
        return Boolean(nextInput("bool", def, title, opts));
      },
      string: function (def, title, opts) {
        return String(nextInput("string", def, title, opts));
      },
    };

    const broker = opts.broker;

    const strategy = {
      long: 1,
      short: -1,
      fixed: "fixed",
      percent_of_equity: "percent_of_equity",
      cash: "cash",
      position_size: 0,
      get position_avg_price() {
        return broker ? broker.avgPrice : NaN;
      },
      get netprofit() {
        return broker ? broker.realized : 0;
      },
      get openprofit() {
        return broker ? broker.unrealized(rt.i) : 0;
      },
      get closedtrades() {
        return broker ? broker.trades.length : 0;
      },
    };

    strategy.init = strategy;
    const strategyFn = function (name, optsArg) {
      if (rt.i !== 0) return;
      const cfg = Object.assign({ name: name || "Strategy" }, optsArg && typeof optsArg === "object" ? optsArg : {});
      if (typeof name === "object") Object.assign(cfg, name);
      rt.strategyConfig = Object.assign(rt.strategyConfig, cfg, { name: cfg.name || name || "Strategy" });
      if (broker) broker.configure(rt.strategyConfig);
    };
    Object.assign(strategyFn, strategy);
    Object.defineProperty(strategyFn, "position_size", {
      get: function () {
        return broker ? broker.position : 0;
      },
    });
    Object.defineProperty(strategyFn, "position_avg_price", {
      get: function () {
        return broker ? broker.avgPrice : NaN;
      },
    });
    strategyFn.entry = function (id, direction, optsArg) {
      const o = optsArg && typeof optsArg === "object" ? optsArg : {};
      broker.entry(String(id), Number(direction), o.qty, rt.i);
    };
    strategyFn.close = function (id) {
      broker.close(id == null ? null : String(id), rt.i);
    };
    strategyFn.close_all = function () {
      broker.close(null, rt.i);
    };
    strategyFn.exit = function (id, fromEntry, optsArg) {
      const o = optsArg && typeof optsArg === "object" ? optsArg : {};
      broker.exit(String(id || "exit"), fromEntry == null ? null : String(fromEntry), o, rt.i);
    };

    function plot(value, titleOrOpts, opts) {
      let title = "Plot";
      let colorVal = color.blue;
      if (typeof titleOrOpts === "string") title = titleOrOpts;
      else if (titleOrOpts && typeof titleOrOpts === "object") {
        title = titleOrOpts.title || title;
        colorVal = titleOrOpts.color || colorVal;
      }
      if (opts && typeof opts === "object") {
        title = opts.title || title;
        colorVal = opts.color || colorVal;
      }
      let rec = plots.find((p) => p.title === title);
      if (!rec) {
        rec = { title, color: colorVal, values: [] };
        plots.push(rec);
      }
      rec.color = colorVal;
      rec.values[rt.i] = Number(value);
    }

    function nz(x, y) {
      const v = Number(x);
      if (!isFiniteNumber(v)) return y == null ? 0 : Number(y);
      return v;
    }

    function na(x) {
      if (arguments.length === 0) return NaN;
      const v = Number(x);
      return !isFiniteNumber(v);
    }

    const math = {
      abs: Math.abs,
      max: Math.max,
      min: Math.min,
      sqrt: Math.sqrt,
      sign: Math.sign,
      ceil: Math.ceil,
      floor: Math.floor,
      round: Math.round,
      pow: Math.pow,
      avg: function () {
        let s = 0;
        for (let i = 0; i < arguments.length; i += 1) s += Number(arguments[i]);
        return s / arguments.length;
      },
    };

    const builtins = {
      ta,
      strategy: strategyFn,
      input,
      color,
      plot,
      plotshape: function () {},
      plotchar: function () {},
      bgcolor: function () {},
      hline: function () {},
      fill: function () {},
      alertcondition: function () {},
      nz,
      na,
      math,
      true: true,
      false: false,
      bar_index: 0,
      hl2: 0,
      hlc3: 0,
      ohlc4: 0,
    };

    const boxes = Object.create(null);
    function boxFor(name) {
      if (!boxes[name]) {
        boxes[name] = makeSeriesProxy((offset) => rt.getVar(name, offset));
      }
      return boxes[name];
    }

    const close = makeSeriesProxy((offset) => {
      const idx = rt.i - offset;
      return idx < 0 ? NaN : bars[idx].close;
    });
    const open = makeSeriesProxy((offset) => {
      const idx = rt.i - offset;
      return idx < 0 ? NaN : bars[idx].open;
    });
    const high = makeSeriesProxy((offset) => {
      const idx = rt.i - offset;
      return idx < 0 ? NaN : bars[idx].high;
    });
    const low = makeSeriesProxy((offset) => {
      const idx = rt.i - offset;
      return idx < 0 ? NaN : bars[idx].low;
    });
    const volume = makeSeriesProxy((offset) => {
      const idx = rt.i - offset;
      return idx < 0 ? NaN : bars[idx].volume;
    });

    const scope = new Proxy(
      {},
      {
        has(_t, prop) {
          if (prop === Symbol.unscopables) return false;
          return true;
        },
        get(_t, prop) {
          if (prop === Symbol.unscopables) return undefined;
          if (prop === "close") return close;
          if (prop === "open") return open;
          if (prop === "high") return high;
          if (prop === "low") return low;
          if (prop === "volume") return volume;
          if (prop === "time") return bars[rt.i].epoch * 1000;
          if (prop === "bar_index") return rt.i;
          if (prop === "last_bar_index") return bars.length - 1;
          if (prop === "hl2") return (bars[rt.i].high + bars[rt.i].low) / 2;
          if (prop === "hlc3")
            return (bars[rt.i].high + bars[rt.i].low + bars[rt.i].close) / 3;
          if (prop === "ohlc4")
            return (bars[rt.i].open + bars[rt.i].high + bars[rt.i].low + bars[rt.i].close) / 4;
          if (Object.prototype.hasOwnProperty.call(builtins, prop)) return builtins[prop];
          if (prop === "strategy") return strategyFn;
          return boxFor(String(prop));
        },
        set(_t, prop, value) {
          rt.setVar(String(prop), value);
          return true;
        },
      }
    );

    rt.scope = scope;
    rt.builtins = builtins;
    rt.inputDefs = inputDefs;
    rt.resetInputSeq = function () {
      inputSeq = 0;
    };
    return rt;
  }

  function compile(jsBody) {
    // new Function is non-strict, which allows `with`.
    return new Function(
      "scope",
      "var window=undefined,document=undefined,globalThis=undefined,Function=undefined,eval=undefined,fetch=undefined;" +
        "with (scope) {\n" +
        jsBody +
        "\n}"
    );
  }

  function runPine(pine, bars, options) {
    if (!bars || !bars.length) throw new Error("No bars to run");
    const js = transpile(pine);
    let fn;
    try {
      fn = compile(js);
    } catch (err) {
      const e = new Error("Pine could not be compiled: " + err.message);
      e.compiled = js;
      throw e;
    }
    const rt = createRuntime(bars, options || {});
    try {
      for (let i = 0; i < bars.length; i += 1) {
        rt.i = i;
        rt.resetInputSeq();
        if (options && options.broker) options.broker.onBarOpen(i);
        fn(rt.scope);
        if (options && options.broker) options.broker.onBarClose(i);
      }
      if (options && options.broker) options.broker.finish(bars.length - 1);
    } catch (err) {
      err.compiled = js;
      err.barIndex = rt.i;
      throw err;
    }
    return {
      compiled: js,
      plots: rt.plots,
      strategyConfig: rt.strategyConfig,
      result: options && options.broker ? options.broker.summary() : null,
    };
  }

  global.NQPine = {
    transpile,
    extractInputs,
    runPine,
    createRuntime,
    compile,
  };
})(typeof window !== "undefined" ? window : globalThis);
