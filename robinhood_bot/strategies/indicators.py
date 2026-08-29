from __future__ import annotations


def sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    ema_value = sum(values[:period]) / period
    for price in values[period:]:
        ema_value = (price - ema_value) * multiplier + ema_value
    return ema_value


def rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None

    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))

    if len(gains) < period:
        return None

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for index in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[index]) / period
        avg_loss = (avg_loss * (period - 1) + losses[index]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period or len(highs) != len(closes) or len(lows) != len(closes):
        return None

    true_ranges: list[float] = []
    for index in range(1, len(closes)):
        high_low = highs[index] - lows[index]
        high_close = abs(highs[index] - closes[index - 1])
        low_close = abs(lows[index] - closes[index - 1])
        true_ranges.append(max(high_low, high_close, low_close))

    if len(true_ranges) < period:
        return None
    return sum(true_ranges[-period:]) / period


def macd(
    values: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float | None, float | None, float | None]:
    if len(values) < slow + signal_period:
        return None, None, None

    macd_line_values: list[float] = []
    for end in range(slow, len(values) + 1):
        window = values[:end]
        fast_ema = ema(window, fast)
        slow_ema = ema(window, slow)
        if fast_ema is None or slow_ema is None:
            continue
        macd_line_values.append(fast_ema - slow_ema)

    if len(macd_line_values) < signal_period:
        return None, None, None

    signal_line = ema(macd_line_values, signal_period)
    macd_line = macd_line_values[-1]
    if signal_line is None:
        return None, None, None
    return macd_line, signal_line, macd_line - signal_line


def bollinger_bands(
    values: list[float],
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[float | None, float | None, float | None]:
    if len(values) < period:
        return None, None, None
    window = values[-period:]
    middle = sum(window) / period
    variance = sum((value - middle) ** 2 for value in window) / period
    band_width = std_dev * (variance ** 0.5)
    return middle - band_width, middle, middle + band_width
