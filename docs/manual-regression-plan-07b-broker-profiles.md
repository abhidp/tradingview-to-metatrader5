# Manual Regression Checklist — Plan 7b (Broker Profiles)

Branch: `plan-07b-broker-profiles` · PR #58 → `v2-desktop`. Run before merging.

## Setup
- [ ] Fully quit any running app + confirm no stray `python`/MT5 left over.
- [ ] Launch: `venv\Scripts\python -m app.desktop`
- [ ] Have ready: **two real MT5 logins** (two Fusion demo accounts with the same Fusion terminal is the easiest; or a second broker with its own terminal installed). Note each account number, password, server, terminal path.
- [ ] Open the Logs tab in a second view / keep the terminal visible.

---

## A. Broker-profiles UI (Settings tab)
- [ ] Settings tab shows a **Broker profiles** section above the MT5 fields.
- [ ] All buttons are clearly visible (no faded/invisible buttons): "Save current settings as a profile…", Activate, Delete, Save profile, Cancel.
- [ ] Click **Save current settings as a profile…** → the form appears (name + password fields).
- [ ] Click **Cancel** → the form hides.
- [ ] Reopen the form → **Save profile** button is **disabled/greyed** while name or password is empty.
- [ ] Type a name only → still disabled. Type a password only → still disabled. Both filled → button **enables**.

## B. Create / validation
- [ ] Save a profile for **Broker 1** (real account + password) → appears in the list.
- [ ] Try to save **another profile with the same name** → blocked with a red banner ("A profile named '…' already exists").
- [ ] Try to save **another profile with the same account + server** (different name) → blocked ("A profile for this broker account already exists").
- [ ] Save a second, genuinely different profile for **Broker 2** → succeeds, list shows both.

## C. Button styling / state
- [ ] The **active** profile's button reads **Active**, is **bright green**, and is not clickable.
- [ ] Inactive profiles' **Activate** buttons are **faded green** and clickable.
- [ ] Spacing: clear gaps between the profile name, the Active/Activate button, and Delete (not squished).

## D. Activation = hot-swap (core)
- [ ] With the engine **running**, click **Activate** on the Broker 2 profile.
- [ ] Terminal shows `🔄 Switching MT5 connection…` then `✅ MT5 Connected: <Broker 2 account>` — **no "Engine stopped", no port error (WinError 10048)**, proxy stays up.
- [ ] Settings fields update to Broker 2; banner shows "Profile activated." and **auto-dismisses** after a few seconds.
- [ ] Place a test trade in TradingView → it **copies to Broker 2** (check Trades tab + MT5).
- [ ] Activate Broker 1 again → reconnects to Broker 1; a new test trade copies there.
- [ ] Repeat the A→B→A switch 2–3 times rapidly → never crashes the proxy, always reconnects.

## E. Activation failure feedback
- [ ] Create a profile with a **wrong password** (or wrong terminal) and activate it.
- [ ] Banner shows **"Profile activated, but MT5 isn't connected — check the account, password, and terminal path."** (not a plain "activated").
- [ ] Dashboard/status MT5 indicator shows disconnected.
- [ ] Re-activate a good profile → reconnects fine (recovers).

## F. Symbol settings are not clobbered
- [ ] Symbols tab: set suffix (e.g. `.r`) + add a symbol override → Save.
- [ ] Activate a profile → confirm the suffix and override are **still present** (not wiped) and trades still resolve the symbol.
- [ ] Save a new profile via "Save current settings…" → it captures the current suffix/map (re-activating it later keeps them).

## G. Delete
- [ ] Delete a **non-active** profile → confirm dialog → it disappears; banner "Profile deleted." auto-dismisses.
- [ ] Delete the **active** profile → it's removed and no profile shows as active.
- [ ] (Optional integrity check) After deleting the active profile, the stored secret `profiles.<id>.password` and the live `mt5.password` are gone.

## H. Persistence
- [ ] With a profile active, **fully restart the app**.
- [ ] The same profile is still marked **Active**, Settings fields reflect it, and trades copy to that broker.

## I. Default profile (fresh onboarding) — optional
- [ ] On a clean DB, run the wizard to completion.
- [ ] Settings tab shows a **Default (active)** profile seeded from the values you entered (correct account/server/terminal/suffix).

## J. Settings "Apply to engine" path
- [ ] Edit an MT5 field in Settings (engine running) → Save → banner offers **Apply to engine**.
- [ ] Click it → applies in place (no proxy restart); banner says "Applied to engine." (or "Apply failed — check status." on error, not a false success).

---

## K. Regression of existing features (make sure nothing broke)
- [ ] Engine **Start** from stopped → connects MT5 + TV, trades copy.
- [ ] Engine **Stop** → clean stop.
- [ ] Normal trade flow: open, partial close, full close, TP/SL update all copy correctly.
- [ ] Manual close on MT5 is detected and closes the TV side.
- [ ] Trades tab paging/filtering works.
- [ ] Symbols tab add/remove/save works.
- [ ] Terminal picker (dropdown + Browse) in Settings and the wizard still works.
- [ ] Tray quit fully exits the app.

---

## Notes / found issues
(record anything off here, plus the results to paste into PR #58)
