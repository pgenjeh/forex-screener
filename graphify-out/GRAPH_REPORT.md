# Graph Report - forex-screener  (2026-11-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 124 nodes · 232 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6559f65a`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- run_scalping
- bot.py
- scheduler.py
- telegram_notify.py
- screener.py
- main
- deploy
- build_scalp_md
- _msnr_str
- find_msnr_levels
- deploy_github.sh
- install_cron.sh
- run_screener.sh script

## God Nodes (most connected - your core abstractions)
1. `main()` - 26 edges
2. `run_scalping()` - 18 edges
3. `handle_update()` - 9 edges
4. `send_text()` - 9 edges
5. `scalp_tf()` - 8 edges
6. `main()` - 7 edges
7. `main()` - 6 edges
8. `build_message()` - 6 edges
9. `send_file()` - 6 edges
10. `build_scalp_md()` - 6 edges

## Surprising Connections (you probably didn't know these)
- `run_scalping()` --calls--> `send_text()`  [EXTRACTED]
  screener.py → telegram_notify.py
- `handle_update()` --calls--> `send_text()`  [EXTRACTED]
  bot.py → telegram_notify.py
- `main()` --calls--> `build_message()`  [EXTRACTED]
  screener.py → telegram_notify.py
- `main()` --calls--> `send_file()`  [EXTRACTED]
  screener.py → telegram_notify.py
- `main()` --calls--> `send_text()`  [EXTRACTED]
  screener.py → telegram_notify.py

## Import Cycles
- None detected.

## Communities (13 total, 3 thin omitted)

### Community 0 - "run_scalping"
Cohesion: 0.11
Nodes (9): analyse_scalp(), current_sessions(), detect_crt(), fetch_yahoo(), find_snr(), latest_crt(), nearest_msnr(), run_scalping() (+1 more)

### Community 1 - "bot.py"
Cohesion: 0.19
Nodes (9): cooldown_left(), get_updates(), handle_update(), is_allowed(), log(), main(), parse_command(), run_screener() (+1 more)

### Community 2 - "scheduler.py"
Cohesion: 0.23
Nodes (6): main(), log(), main(), market_open(), run_screener(), telegram_times()

### Community 3 - "telegram_notify.py"
Cohesion: 0.21
Nodes (6): build_message(), get_config(), main(), send_file(), send_text(), _td_line()

### Community 4 - "screener.py"
Cohesion: 0.23
Nodes (7): analyse(), atr(), ema(), rsi(), scalp_tf(), sma(), stochastic()

### Community 5 - "main"
Cohesion: 0.18
Nodes (6): build_topdown(), main(), print_topdown(), resample_4h(), _snr_status(), _snr_str()

### Community 6 - "deploy"
Cohesion: 0.22
Nodes (8): build, builder, dockerfilePath, deploy, restartPolicyMaxRetries, restartPolicyType, startCommand, $schema

### Community 7 - "build_scalp_md"
Cohesion: 0.33
Nodes (5): build_scalp_md(), _crt_short(), fmt_price(), print_scalp(), print_table()

### Community 8 - "_msnr_str"
Cohesion: 0.40
Nodes (3): _crt_str(), _msnr_str(), print_msnr_crt()

### Community 9 - "find_msnr_levels"
Cohesion: 0.67
Nodes (3): find_msnr_levels(), add(), near()

## Knowledge Gaps
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `main()` connect `main` to `run_scalping`, `scheduler.py`, `telegram_notify.py`, `screener.py`, `build_scalp_md`, `_msnr_str`, `find_msnr_levels`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Should `run_scalping` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._
- **Why does `send_text()` connect `telegram_notify.py` to `run_scalping`, `bot.py`, `screener.py`, `main`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `run_scalping()` connect `run_scalping` to `scheduler.py`, `telegram_notify.py`, `screener.py`, `main`, `build_scalp_md`, `find_msnr_levels`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._