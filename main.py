"""btc-race-24h-20261117-0603: patient trend rider for cbBTC (CBBTC/USDC).

Strategy, in plain words (hello, batch, orders, bar):
- Enter once, early: on the first batch at or after bar 24, buy with all cash.
  The entry is persistent: if the buy is rejected (for example a warm-up batch),
  it is retried on the next batch, so the bot never strands itself flat.
- Bank the trend: while holding, sell everything once the close is 100 bps above
  the close of the bar on which the buy was decided.
- Re-enter on dips: after an exit, buy again only when the fast EMA (60 bars) is
  above the slow EMA (240 bars) and the close has dipped at least 80 bps below
  the fast EMA. No dip, no trade.
- Crash insurance: while holding, a trailing stop sells everything if the close
  falls 300 bps below the highest close since entry.
- State is reconciled from the fills every batch: the bot only believes it holds
  a position when the account says so, so a rejected order can never strand it.

Everything is deterministic: fixed parameters, no clock, no network, no files
outside the repository, no randomness. EMAs are updated incrementally from the
closes as they arrive, seeded with the first close.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
ENTRY_BAR = 24
FAST_N = 60
SLOW_N = 240
TARGET_BPS = 100
DIP_BPS = 80
STOP_BPS = 300
MAX_SLIP_BPS = 500


class Bot:
    def __init__(self):
        self.closes = []
        self.ema_fast = None
        self.ema_slow = None
        self.in_pos = False
        self.armed = False      # may re-enter on a dip (after the first exit)
        self.entered = False    # initial entry fill seen
        self.entry_close = 0    # close of the bar the buy was decided on
        self.decision_close = 0  # close of the latest bar a buy was decided on
        self.peak_close = 0

    def _ema_update(self, close):
        kf = 2.0 / (FAST_N + 1)
        ks = 2.0 / (SLOW_N + 1)
        if self.ema_fast is None:
            self.ema_fast = float(close)
            self.ema_slow = float(close)
        else:
            self.ema_fast = close * kf + self.ema_fast * (1 - kf)
            self.ema_slow = close * ks + self.ema_slow * (1 - ks)

    def on_batch(self, state, batch):
        if state.warming_up:
            return []
        bar = state.latest.get(SYMBOL)
        if bar is None:
            return []
        close = int(bar["c"])
        self.closes.append(close)
        self._ema_update(close)
        i = len(self.closes) - 1

        pos = state.positions.get(SYMBOL)
        holding = pos is not None and pos.qty > 0
        if holding and not self.in_pos:
            # The buy filled on this bar: the decision was made on the previous bar.
            self.in_pos = True
            self.entered = True
            self.entry_close = self.decision_close
            self.peak_close = max(self.decision_close, close)
        elif not holding and self.in_pos:
            self.in_pos = False
            self.armed = True

        if holding:
            if close > self.peak_close:
                self.peak_close = close
            # Profit target: 100 bps above the decision-bar close.
            if close * 10000 >= self.entry_close * (10000 + TARGET_BPS):
                return [{"side": "sell", "symbol": SYMBOL, "qty": pos.qty,
                         "max_slippage_bps": MAX_SLIP_BPS}]
            # Trailing stop: 300 bps below the highest close since entry.
            if close * 10000 <= self.peak_close * (10000 - STOP_BPS):
                return [{"side": "sell", "symbol": SYMBOL, "qty": pos.qty,
                         "max_slippage_bps": MAX_SLIP_BPS}]
            return []

        # Flat: initial entry, first batch at or after bar 24 (retried if rejected).
        if not self.entered and i >= ENTRY_BAR:
            self.decision_close = close
            return [{"side": "buy", "symbol": SYMBOL,
                     "notional_quote_units": state.cash,
                     "max_slippage_bps": MAX_SLIP_BPS}]
        # Flat: dip re-entry after an exit, only in an uptrend.
        if self.armed and i > SLOW_N and self.ema_fast > self.ema_slow:
            if close * 10000 <= int(self.ema_fast) * (10000 - DIP_BPS):
                self.decision_close = close
                return [{"side": "buy", "symbol": SYMBOL,
                         "notional_quote_units": state.cash,
                         "max_slippage_bps": MAX_SLIP_BPS}]
        return []


makefun_bars.run(Bot().on_batch)
