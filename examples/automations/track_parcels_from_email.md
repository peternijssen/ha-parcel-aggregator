# Automatic parcel tracking from e-mail (IMAP → carrier integrations)

Companion guide for [`track_parcels_from_email.yaml`](track_parcels_from_email.yaml): watch your mailbox(es) for shipping e-mails, extract the tracking number, and register it with a parcel integration — fully automatic, no custom component required. New parcels simply appear in the aggregator the moment the shipping confirmation lands in your inbox.

**How it works, in one line:** the core [IMAP integration](https://www.home-assistant.io/integrations/imap/) fires an `imap_content` event for every new e-mail (including the body); the automation extracts tracking numbers — cheap regexes first, an optional AI fallback for everything else — and calls the carrier's `track_parcel` action.

```
new e-mail ──imap_content──▶ automation ──▶ regex match?  ──▶ gls.track_parcel /
                                     │                        dragonfly.track_parcel
                                     └──▶ no match, but looks like a shipping mail
                                          ──▶ ai_task.generate_data (optional)
                                              ──▶ carrier + tracking number
```

This complements the aggregator: account-based carriers (DHL, PostNL, DPD) discover parcels through your carrier account, while code-based carriers ([GLS](https://github.com/ha-parcel-integrations/ha-gls), [Dragonfly](https://github.com/ha-parcel-integrations/ha-dragonfly)) need each tracking number registered — this recipe automates exactly that step, and everything flows into the aggregator as usual.

## Prerequisites

- One or more parcel integrations that expose a *track parcel* action:
  - [ha-gls](https://github.com/ha-parcel-integrations/ha-gls) — `gls.track_parcel` (field `parcel_no`)
  - [ha-dragonfly](https://github.com/ha-parcel-integrations/ha-dragonfly) — `dragonfly.track_parcel` (field `tracking_code`)
- The core **IMAP** integration (no HACS needed).
- *(Optional but recommended)* an **AI Task** entity (e.g. Anthropic/Claude, Google, OpenAI) for the fallback path. Without it, simply delete the fallback branch — the regex paths work standalone.

## Step 1 — IMAP entries

Add **Settings → Devices & services → Add integration → IMAP** for every account you want to watch:

| Field | Value |
|---|---|
| Server | `imap.gmail.com` (Gmail) — mind the hostname, it is **not** `imap.google.com` |
| Port | `993` |
| Username | your address |
| Password | see the Gmail note below |
| Charset | `utf-8` |
| Folder | `INBOX` (or a label/subfolder — see below) |

Then open the entry's **Configure** (options) and set:

- **Message data to include in the event**: enable **text** (the automation needs the body!)
- **Max message size**: raise it to `30000` — carrier mails are long and the default cuts them off before the tracking number appears.
- Leave *search* on `UnSeen UnDeleted` and *push* enabled (IMAP IDLE → events arrive within seconds).

**Multiple mailboxes / accounts:** each IMAP entry is one account × folder combination. Add the same account again with a different folder to watch labels (Gmail labels appear as IMAP folders). All entries fire the *same* `imap_content` event, so **one automation covers all of them** — the event data tells you which entry it came from if you ever need it.

**Gmail note:** since May 2025 Google blocks plain-password IMAP logins ("less secure apps"). Use an **app password** instead (requires 2-step verification): <https://myaccount.google.com/apppasswords>. App passwords are Google's explicitly supported exception, not a deprecated leftover.

## Step 2 — the automation

Paste [`track_parcels_from_email.yaml`](track_parcels_from_email.yaml) and adapt the notify action, the keyword list and the AI entity to your setup.

### Design notes

- **Regex first, AI second.** Mails straight from the carrier match a cheap regex and never touch the AI. The AI fallback earns its keep on the messy cases: forwarded mails ("Fwd:" from your own address), webshop confirmations, unfamiliar layouts. In a real-world test it pulled the correct GLS parcel number out of a forwarded mail while ignoring a second code embedded in the T&T links, a sender reference and several dates.
- **Adding a carrier is two lines of concept:** a regex variable + a `repeat` block calling its `track_parcel` action. Everything the regexes don't know yet is still *visible* via the AI "carrier not supported" notification, so you learn which carrier to add next.
- **Duplicates are harmless:** calling `track_parcel` twice for the same number is a no-op in the carrier integrations, and the `initial` condition already suppresses re-triggers of the same message.
- **`mode: queued`** so a burst of mails (mailbox sync) is processed one by one instead of being dropped.

## Pitfalls we hit so you don't have to

1. **Jinja eats backslashes in string literals.** A template stored as `regex_findall('\bAMZNL…')` silently becomes a **backspace character** (`\b` is a string escape), so the regex never matches — no error anywhere. That's why every pattern in the example is backslash-free: `(?<![0-9])`/`(?![0-9])` lookarounds instead of `\b`, `[0-9]` instead of `\d`. Copy that style for new carriers.
2. **The `initial` event flag means the opposite of what you might expect.** In the IMAP integration `initial: true` = *first time this message is seen* (new mail); `false` = a duplicate trigger of the same message. So the condition must **require** `initial`, not exclude it. (Requiring it doubles as restart/reconnect dedup.)
3. **Raise the max message size.** With the default the body is truncated before the tracking number appears in most carrier mails. `30000` is plenty.
4. **Enable "text" in the event options.** Without it the event has headers only and there is nothing to extract.
5. **Gmail = app password.** Plain passwords stopped working on Google IMAP in May 2025; app passwords (with 2FA) are the supported route. And the host is `imap.gmail.com`.
6. **Digit-run regexes match phone numbers too.** An 11-digit Dutch phone number in international notation (`31…`) sits inside the 11–14 digit GLS range; the `reject('match', '31[0-9]{9}$')` filter drops it. Adapt to your country code if needed.

## Testing without waiting for a real parcel

Fire a fake event and watch the automation trace (Settings → Automations → your automation → Traces):

```bash
curl -X POST -H "Authorization: Bearer $HA_TOKEN" -H "Content-Type: application/json" \
  http://YOUR_HA:8123/api/events/imap_content \
  -d '{"sender":"noreply@gls-netherlands.com","subject":"Your GLS parcel",
       "text":"Parcel number: 12345678901234","initial":true,"folder":"INBOX","username":"test"}'
```

Then `untrack_parcel` the test number afterwards. For a full end-to-end test, forward a real shipping mail to the watched mailbox — it must arrive **unread**.
