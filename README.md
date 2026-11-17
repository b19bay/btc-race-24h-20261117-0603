[![make.fun · btc-race-24h-20261117-0603](https://make.fun/badge/btc-race-24h-20261117-0603.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![rank](https://make.fun/badge/btc-race-24h-20261117-0603/b19bay/btc-race-24h-20261117-0603/rank.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)
[![reward](https://make.fun/badge/btc-race-24h-20261117-0603/b19bay/btc-race-24h-20261117-0603/reward.svg)](https://make.fun/bounty/btc-race-24h-20261117-0603?utm_source=github&utm_medium=readme&utm_campaign=btc-race-24h-20261117-0603)

# btc-race-24h-20261117-0603 — Patient Trend Rider

A long-only cbBTC (CBBTC/USDC) trading bot for the make.fun 24-hour live race.
It trades rarely, banks confirmed moves, and sits out chop.

## Strategy (main.py, Python 3.13 stdlib only)

1. **Enter once, early.** On the first batch at or after bar 24, buy with all cash.
   The entry is persistent: if the buy is rejected (e.g. a warm-up batch), it is
   retried on the next batch, so the bot never strands itself flat.
2. **Bank the trend.** While holding, sell everything once the close is 100 bps
   above the close of the bar on which the buy was decided.
3. **Re-enter on dips.** After an exit, buy again only when the fast EMA (60 bars)
   is above the slow EMA (240 bars) and the close has dipped at least 80 bps
   below the fast EMA. No dip, no trade.
4. **Crash insurance.** While holding, a trailing stop sells everything if the
   close falls 300 bps below the highest close since entry. After a stop exit
   the bot waits 120 bars before any dip re-entry (round 2).
5. **Gated open (round 2).** The first buy waits while the trailing 24-bar
   return is worse than -50 bps, and buys at bar 240 at the latest no matter
   what — so a steeply falling open cannot strand the bot long at the top.
5. **Fill-driven state.** The bot only believes it holds a position when the
   account says so, so a rejected order can never strand it. No clock, no
   network, no files outside the repository, no randomness — fully deterministic.

`vendor/makefun_bars.py` is the kit's Python SDK shim, copied byte-for-byte.

## Local validation (kit scorer, grade-local --driver process)

Dev window (1,440 one-minute bars, frozen):

| metric | value |
|---|---|
| net PnL | **+$14.128** |
| trades | 4 (2 round trips) |
| rejected orders | 0 |
| fees | $1.612 |
| max drawdown | 1.734% |
| determinism | two grade-local runs give identical `action_log_sha256` (`1d1ee5f2…`) and `result_sha256` (`384362c7…`) |

Trades on the dev window: buy bar 25 @ $64,481.94 → sell bar 511 @ $65,013.28;
buy bar 554 @ $64,261.90 → sell bar 655 @ $64,740.76.

## Robustness (offline replay with an exact port of the harness fill model)

The simulator reproduces the official grades of buy-and-hold (+$1.067) and
momentum (+$2.446) to the unit, so its numbers are trustworthy.

- Split halves as independent windows: first half +$14.13 (4 trades), second
  half +$7.30 (2 trades) — both positive.
- Parameter plateau around the chosen point (target 100 bps, dip 80 bps):
  target 100 with dip 60–90 bps all give worst-half ≥ +$7.30 and full-window
  +$13.76–$14.13. The 300 bps stop never triggers on the dev window; it is
  crash insurance for the unseen race window only.
- What was rejected: Donchian breakouts, EMA crossovers (8/21 lost −$106),
  hourly regime switching (−$59 to −$105) — on this window every frequent-trading
  family loses to the ~26 bps round-trip cost and chop. The chosen design trades
  2 round trips per day instead.

## Round 2 — what was tried, what changed

The v1 numbers were already at the top of the parameter grid (target 60–150,
dip 40–120, stop 200–800, entry bar 12–120, EMA 30/120–120/480): no grid point
beats worst-half +$7.30 / full +$14.13. Structural additions were all rejected
on the maximin criterion — partial profit-taking (full +$10.17, worst +$5.31),
time exits (best +$6.54), and a separate higher re-entry target (+$15.98 full
but only by fitting one leg's +148 bps peak; halves get worse at 150+ bps, so
it was rejected as overfit). The stop is inert on the dev window (never
triggers), as are the ratchet and hard-stop variants.

Two genuine refinements shipped instead, each as its own commit and each
re-graded with the official scorer:

1. **Gated open** (`ca24b0d`): buy waits while the trailing 24-bar return is
   worse than -50 bps (binds on ~6.6% of bars; dev open is -12 bps, so it
   passes at bar 24), deadline bar 240.
2. **Stop-exit cooldown** (`2979e2c`): 120 bars with no dip re-entry after a
   trailing-stop exit.

Neither fires on the dev window, so the official grade is unchanged — and the
real `main.py` (not a port) was re-run through the offline simulator on every
window to prove it: full +$14.128 (4 trades), halves +$14.13 / +$7.30, quarters
-$4.68 / +$9.78 / +$7.30 / -$0.26 (the quarter losses are slicing artifacts:
a leg opened in the quarter is flattened at its boundary before the target).

Final numbers are the same as v1's — the round-2 work is race-window insurance
and the transcript-gate fix (main.py now revised in two separate commits),
not a dev-window PnL gain.

## Grade locally

```sh
node <kit>/cli/makefun.mjs grade-local --kit <kit> --bot <this repo> --driver process
```

Note: the process driver runs Node bots only; a Python bot needs Docker on the
server, or a small Node proxy that forwards the NDJSON lines to `python3 -P -s
main.py` (used for the numbers above; the proxy is a local validation aid only
and is not part of this entry).
