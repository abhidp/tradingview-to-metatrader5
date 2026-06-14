# TV2MT5 Desktop — Plan 2 Design: Broker Adapter + Settings Store

**Date:** 2026-06-14
**Status:** Approved for planning
**Author:** Abhi D (with Claude)
**Parent spec:** `docs/superpowers/specs/2026-06-13-tv2mt5-desktop-design.md`
**Roadmap row:** Plan 2 of `docs/superpowers/plans/2026-06-13-tv2mt5-desktop-plan-roadmap.md`

## Problem

Plan 1 collapsed the infrastructure (SQLite + in-process queue, one process). Two
things are still hard-wired in ways that block the UI, the wizard, and multi-broker
support:

1. **Configuration lives in `.env`.** `TV_BROKER_URL`, `TV_ACCOUNT_ID`, the MT5
   credentials, and the symbol suffix/map are read with `os.getenv` at import time
   across `src/config/mt5_config.py`, `src/config/mt5_symbol_config.py`,
   `src/services/tradingview_service.py`, and `src/core/interceptor.py`. A
   non-technical trader cannot hand-edit `.env`, and the future Settings UI (Plan 3)
   needs a writable store, not a file.

2. **Broker-specific matching is inlined in the interceptor.** `interceptor.py`
   computes `base_path = "{TV_BROKER_URL}/accounts/{TV_ACCOUNT_ID}"` and decides
   which flows to process in `should_log_request`. There is no seam where a broker's
   identity is defined, and `broker_url`/`account_id` must be discovered by hand and
   typed into `.env`.

## Goal

Introduce two seams from the parent spec without touching the proven trade-execution
path:

- A **`SettingsStore`** backed by a SQLite `settings` table that replaces `.env` as
  the source of truth, seeded once from any existing `.env`.
- A **`BrokerAdapter`** interface with a **`FusionMarketsAdapter`** that owns flow
  matching and **auto-detects `broker_url` + `account_id` from live traffic**,
  persisting them to settings.

At the end of Plan 2, trades still copy TV→MT5 exactly as before, but configuration
is database-backed and the broker identity is discovered automatically rather than
hand-entered.

## Non-Goals

- **No change to trade parsing/execution.** The ~355 lines in `trade_handler.py`
  (`process_order` / `process_execution` / `process_position_close` /
  `process_position_update` / `process_tpsl_delete`) and the MT5 service stay
  byte-for-byte. The parent spec is explicit: not a rewrite of the working logic.
- **No UI.** The Settings UI and the onboarding wizard are Plans 3–4. Plan 2 exposes
  the store and adapter as Python APIs only.
- **No encryption implementation.** A `SecretBox` seam is added with a plaintext
  default; DPAPI / OS-keyring is a later, isolated follow-up.
- **No second broker.** Only `FusionMarketsAdapter` ships. The interface is proven
  by one implementation.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Adapter depth | **Thin** — adapter owns `matches` + `detect_account`; trade parsing stays in `trade_handler` | The parse logic is TradingView's broker-panel REST shape (shared across TV-panel brokers), not Fusion-specific. Per-broker variance is `broker_url`/`account_id`/symbol naming — all config. Full per-broker parse extraction would rewrite the most fragile proven code for no multi-broker gain. |
| `.env` migration | **Seed once** — import `.env` into the `settings` table on first run, then SQLite is canonical and `.env` is ignored | One code path after seeding; friendly to the author's existing setup; clean for new users. |
| Secret storage | **Plaintext behind a `SecretBox` seam** (default `PlaintextSecretBox`, prefix-marked) | Same exposure as today's plaintext `.env`; the DB never leaves the machine or the repo (gitignored, lives in `%APPDATA%`). DPAPI doesn't stop the dominant threat (malware running as the user), so it's deferred behind a clean seam. |
| Settings value typing | Strings in the column; typed accessors (`get_int`, `get_json`, `get_bool`, `get_secret`) | SQLite is dynamically typed; one TEXT column + typed accessors keeps the schema trivial and the API explicit. |
| Auto-detect trigger | On any flow the adapter matches, extract `broker_url`/`account_id` and persist if absent or changed | Removes the manual `TV_BROKER_URL`/`TV_ACCOUNT_ID` step; seeds wizard Step 4 (Plan 4). |

## Architecture

```
                       ┌──────────────────────────────────────────┐
                       │  SettingsStore  (SQLite `settings` table)  │
   .env (first run) ──▶│   seed-once import → canonical thereafter  │
                       │   get/set + typed accessors                │
                       │   secrets via SecretBox (plaintext default)│
                       └───────────────┬────────────────────────────┘
                                       │ reads/writes
        ┌──────────────────────────────┼───────────────────────────────┐
        │                              │                                │
  mt5 config accessors        tv target accessors            symbol settings
  (account/password/           (broker_url/account_id)       (suffix / map)
   server/terminal_path)
                                       │
                                       ▼
   mitmproxy flow ─▶ TradingViewInterceptor ─▶ BrokerAdapter (FusionMarketsAdapter)
                          │                        ├─ matches(flow) -> bool
                          │                        └─ detect_account(flow) -> AccountInfo?
                          │                              │ persists broker_url/account_id
                          ▼                              ▼
                    (unchanged) trade_handler  ◀── parsing stays here, untouched
```

### Components

**New:**
- `app/storage/__init__.py`
- `app/storage/settings_store.py` — `Settings` SQLAlchemy model (on the shared engine
  from `src/config/database.py`) + `SettingsStore` with `get`/`set`/`get_int`/
  `get_json`/`get_bool`/`get_secret`/`set_secret`/`all()`. Seed-once import from `.env`.
- `app/storage/secret_box.py` — `SecretBox` Protocol + `PlaintextSecretBox`
  (default). Stored form is prefix-marked (`plain:<value>`) so the format is
  self-describing and a future `DpapiSecretBox` can coexist + migrate.
- `app/adapters/__init__.py`
- `app/adapters/base.py` — `BrokerAdapter` Protocol + `AccountInfo` dataclass
  (`broker_url: str`, `account_id: str`).
- `app/adapters/fusion_markets.py` — `FusionMarketsAdapter` (`matches`, `detect_account`).
- `app/config_accessors.py` — store-backed replacements for the import-time `os.getenv`
  constants: `get_mt5_config()`, `get_tv_target()`, `get_symbol_settings()`.

**Modified:**
- `src/core/interceptor.py` — accept an injected `BrokerAdapter`; derive `base_path`
  and the match decision from the adapter; run auto-detect; read TV target from the
  store instead of module-level `os.getenv`.
- `src/config/mt5_config.py` — `MT5_CONFIG` becomes a store-backed accessor
  (`get_mt5_config()`); keep a backwards-compatible name for current callers.
- `src/config/mt5_symbol_config.py` — `DEFAULT_SUFFIX`/`SYMBOL_MAP` read from the store.
- `src/services/tradingview_service.py` — `base_url` built from the store.
- `app/engine.py` — construct the `SettingsStore`, run seed-once, construct the
  `FusionMarketsAdapter`, and inject the adapter into the interceptor.

**Unchanged (explicitly):** `src/core/trade_handler.py`, `src/services/mt5_service.py`,
`src/utils/symbol_mapper.py`, `src/workers/mt5_worker.py` (beyond reading config through
the new accessors), `app/queue/inproc_queue.py`.

### Interfaces

```python
# app/storage/secret_box.py
class SecretBox(Protocol):
    def protect(self, plaintext: str) -> str: ...   # returns stored form
    def unprotect(self, stored: str) -> str: ...     # returns plaintext

class PlaintextSecretBox:                            # Plan 2 default
    PREFIX = "plain:"
    def protect(self, s: str) -> str: return f"{self.PREFIX}{s}"
    def unprotect(self, s: str) -> str:
        return s[len(self.PREFIX):] if s.startswith(self.PREFIX) else s

# app/storage/settings_store.py
class SettingsStore:
    def __init__(self, secret_box: SecretBox | None = None): ...
    def get(self, key: str, default: str | None = None) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def get_int(self, key: str, default: int | None = None) -> int | None: ...
    def get_json(self, key: str, default=None): ...
    def get_bool(self, key: str, default: bool = False) -> bool: ...
    def get_secret(self, key: str) -> str | None: ...      # via SecretBox.unprotect
    def set_secret(self, key: str, value: str) -> None: ... # via SecretBox.protect
    def all(self, *, redact_secrets: bool = True) -> dict[str, str]: ...
    def seed_from_env_once(self) -> bool: ...   # returns True if it seeded this call

# app/adapters/base.py
@dataclass
class AccountInfo:
    broker_url: str
    account_id: str

class BrokerAdapter(Protocol):
    name: str
    def matches(self, flow) -> bool: ...                 # is this flow ours to process?
    def detect_account(self, flow) -> AccountInfo | None: ...  # learn broker_url/account_id
```

`parse_trade` from the parent spec's Protocol is intentionally **not** implemented in
Plan 2 — the thin adapter leaves parsing in `trade_handler`. The method remains in the
parent spec for a future non-TradingView-panel broker that needs its own parsing.

### Settings keys (canonical names)

| Key | Type | Secret | Seeded from `.env` |
|-----|------|--------|--------------------|
| `tv.broker_url` | str | no | `TV_BROKER_URL` |
| `tv.account_id` | str | no | `TV_ACCOUNT_ID` |
| `mt5.account` | int | no | `MT5_ACCOUNT` |
| `mt5.password` | str | **yes** | `MT5_PASSWORD` |
| `mt5.server` | str | no | `MT5_SERVER` |
| `mt5.terminal_path` | str | no | `MT5_TERMINAL_PATH` |
| `symbols.default_suffix` | str | no | `MT5_DEFAULT_SUFFIX` |
| `symbols.map` | json | no | `MT5_SYMBOL_MAP` |
| `meta.seeded` | bool | no | — (set to `1` after first seed) |

## Data Flow

**Startup (engine):** build `SettingsStore` → `seed_from_env_once()` (no-op if
`meta.seeded`) → build `FusionMarketsAdapter` → inject adapter into the interceptor →
config accessors and `tradingview_service` read their values from the store.

**Per flow (interceptor):**
1. `adapter.matches(flow)` replaces the inlined `should_log_request` base-path/endpoint
   gating. Non-matching flows return early as today.
2. `adapter.detect_account(flow)` extracts `broker_url`/`account_id` from a TradingView
   broker-panel URL (`https://{host}/accounts/{digits}/...`, gated to TradingView
   origin/referer to avoid false positives). If absent in the store or changed, persist
   them. Detection is idempotent and cheap.
3. Matching flows are handed to the existing `trade_handler` methods unchanged.

## Error Handling

- **Missing required settings** (e.g. no MT5 credentials yet): accessors return `None`
  / raise a clear `MissingSettingError`, not a bare `KeyError`. The engine surfaces a
  readable message; full UI banner states are Plan 3.
- **Malformed `symbols.map` JSON:** `get_json` returns the default (`{}`) and logs a
  warning, matching today's `json.JSONDecodeError` fallback.
- **Auto-detect ambiguity:** if a flow doesn't cleanly match the
  `/accounts/{id}/` pattern under a TradingView origin, `detect_account` returns `None`
  and nothing is written — never guess.
- **Secret round-trip:** `get_secret` on an unprefixed legacy value returns it verbatim
  (forward-compatible), so a value written before the seam can still be read.

## Testing

Unit tests only (Plan 2 ships no UI); manual end-to-end is the existing test-trade path.

- **SettingsStore:** typed round-trips (`get`/`set`, `get_int`, `get_json`, `get_bool`);
  secret round-trip through `PlaintextSecretBox` (stored form is prefixed, `get_secret`
  returns plaintext); `all(redact_secrets=True)` masks secret keys.
- **Seed-once:** seeding from a monkeypatched env populates the table and sets
  `meta.seeded`; a second call is a no-op and does not overwrite manual edits.
- **SecretBox:** `PlaintextSecretBox` protect/unprotect inverse; `unprotect` of an
  unprefixed value is identity.
- **FusionMarketsAdapter.matches:** sample URLs for orders / executions / position
  PUT+DELETE / TP-SL DELETE return `True`; unrelated URLs and wrong methods return
  `False` — parity with the current `should_log_request`.
- **FusionMarketsAdapter.detect_account:** a TradingView broker-panel URL yields the
  right `broker_url`/`account_id`; a non-TradingView or malformed URL yields `None`.
- **Interceptor injection:** the interceptor accepts an injected adapter and matches
  flows via it (mirrors Plan 1's injection tests); auto-detect persists to the store.

## Migration & Compatibility

- **Seed-once import:** on first run, read the existing `.env` keys (via `dotenv`/
  `os.getenv`) into the canonical settings keys, then set `meta.seeded`. Thereafter the
  store is authoritative and `.env` is neither read nor required.
- **`.env` stays gitignored** (`*.env`, `.env`) and the SQLite DB lives in
  `%APPDATA%\TV2MT5` (gitignored `*.db`) — neither is ever committed; the DB never
  leaves the user's machine.
- **Standalone scripts** (`src/scripts/manage_symbols.py`, `src/scripts/start_proxy.py`)
  are not on the single-process runtime path; retargeting them to the store is noted as
  a follow-up, not Plan 2 scope. The runtime path (engine → interceptor → worker) reads
  exclusively from the store after seeding.

## Future (not in scope now)

- **`DpapiSecretBox`** (or Windows Credential Manager / OS keyring) behind the existing
  `SecretBox` seam, with a one-pass migration that re-wraps `plain:`-prefixed values.
- **`parse_trade` in a real second adapter** for any broker that does *not* use
  TradingView's broker panel and therefore needs its own parsing.
- **Shared `TradingViewBrokerAdapter` base** so multiple TV-panel brokers reuse the
  parse path with thin per-broker overrides (host match + default suffix).
- **Settings UI + auto-detect surfaced in the wizard** (Plans 3–4) build directly on
  this store and adapter.
