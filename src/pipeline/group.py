"""Group stage: code assigns membership; the `group` model role only names/describes issues.

Every completed complaint/cancellation record gets exactly one ``issue_id = <topic>.<theme>``.
The theme is the first rule (fixed priority order per topic, THEME_RULES_VERSION) whose entity
names or text regex match; otherwise ``<topic>.general``. Membership never depends on model output.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from pipeline.claims import _csv_text
from pipeline.context import StageContext
from pipeline.io import atomic_write_json, atomic_write_text, dumps_line
from pipeline.rank import mean_string
from pipeline.rowhash import RANKED_INTENTS, TOPICS, canonical
from pipeline.verify import StageCache, cached_chat, chat_model_name, parse_json_payload, sha256_hex

STAGE = "group"
THEME_RULES_VERSION = "themes-v1"
PROMPT_VERSION = "group-names-v1"

# (theme, entity names that trigger it, text regex on lowercased review_text). First match wins.
# Entities are matched by exact (lowercased) name; only lexicon terms whose needles are precise are used.
THEME_RULES: Dict[str, List[Tuple[str, Tuple[str, ...], str]]] = {
    "access": [
        ("account_security", (), r"hack|stolen|compromis|someone else|unauthori[sz]ed|suspicious|not my account"),
        ("password_reset", ("password",), r"password|reset|verification code|\bcode\b|\botp\b|magic link|e-?mail link"),
        ("third_party_login", (), r"facebook|\bfb\b|google|apple id|sign in with|continue with"),
        ("signup", ("signup",), r"sign ?up|regist|create (an |my |a )?account|new account"),
        ("login", ("login",), r"log ?in|logg|sign ?in|signed out|log ?out|kicked out|account"),
    ],
    "usability": [
        ("ads", (), r"\bads?\b|advert|commercials?\b"),
        ("shuffle_queue", ("shuffle", "queue"), r"shuffl|queue|repeat|\bskip|next song|autoplay"),
        ("playlist_library", ("playlist",), r"play ?lists?|library|liked songs|\bliked\b|saved songs|\bsort|folder"),
        ("controls", (), r"button|widget|lock ?screen|notification|control|swipe|gesture|sleep timer|mini ?player"),
        ("ui_redesign", (), r"layout|design|interface|\bui\b|home ?(screen|page)|new look|\bfeed\b|scroll|tik ?tok"
                            r"|vertical|now playing|clutter|dark mode|font|canvas|updat"),
        ("navigation", (), r"navigat|menu|\btabs?\b|confus|hard to (use|find)|complicated|not user friendly|intuitive"),
    ],
    "playback": [
        ("crash", ("crash",), r"crash|force clos|keeps? closing|closes|shuts? down|not respond|black screen"
                              r"|won'?t open|doesn'?t open|not open|can'?t open|won'?t (start|launch)"),
        ("resources", (), r"battery|drain|storage|memory|\bram\b|cache|heat|overheat|data usage|\bcpu\b"),
        ("devices", (), r"bluetooth|\bcar\b|android auto|carplay|chromecast|spotify connect|speakers?\b"
                        r"|smart ?watch|wear ?os|\bwatch\b|\btv\b|alexa|google home|headphones?|earbuds|airpods"),
        ("connection", (), r"connection|internet|wi-?fi|network|no signal|server|cellular|mobile data|\boffline\b"),
        ("stops_pausing", (), r"\bstops?\b|stopp|paus|interrupt|cuts? (out|off)|background|screen (is )?(off|lock)"
                              r"|skips? (songs?|by itself|on its own|randomly)"),
        ("lag_loading", (), r"\blag|buffer|load|slow|freez|stutter|delay|glitch|takes forever|frozen"),
        ("audio_quality", ("audio_quality",), r"sound|audio|quality|volume|bass|equali[sz]er|loud|quiet|distort|crackl"),
    ],
    "downloads": [
        ("disappearing", (), r"disappear|delet|\bgone\b|\blost\b|vanish|remov|re-?download|wiped|missing"),
        ("storage", (), r"storage|sd ?card|\bspace\b|memory|\bgb\b"),
        ("offline_playback", (), r"offline|no (internet|connection|signal)|airplane|flight mode|without (internet|wi-?fi|data)"),
        ("download_failure", ("download",), r"download"),
    ],
    "catalog": [
        ("lyrics", ("lyrics",), r"lyric"),
        ("podcasts_audiobooks", (), r"podcast|audiobook|episode|\bshows?\b"),
        ("missing_content", (), r"missing|not available|unavailable|gr[ae]y(ed)? out|removed|region|country|taken down"
                                r"|no longer|isn'?t on|aren'?t on|not on spotify|doesn'?t have|don'?t have"),
        ("recommendations", ("recommendation",), r"recommend|suggest|algorithm|discover|same (songs?|music|artists?)"
                                                 r"|repetitiv|daily mix|radio|\bdj\b|release radar|for you"),
        ("search", ("search",), r"search|can'?t find|cannot find|\bfind\b"),
    ],
    "billing": [
        ("charge_refund", ("refund",), r"charg|refund|money back|billed|billing|payment|deduct|\bcard\b|scam|fraud"
                                       r"|twice|unauthori[sz]ed"),
        ("cancel_subscription", (), r"cancel|unsubscrib"),
        ("premium_entitlement", (), r"premium.{0,40}(not work|n'?t work|lost|expired|gone|activat|recogni|revert|disappear)"
                                    r"|(lost|lose|activat|restore|revert).{0,30}premium|family plan|\bduo\b|student|verif"),
        ("free_tier_limits", (), r"\bfree\b|pay to|paywall|have to pay|premium only|only (for )?premium|skip limit"
                                 r"|limited skips|(6|six) skips|can'?t (choose|pick|select)|forced? (to )?shuffle"),
        ("price", (), r"price|expensive|\bcost|afford|increase|raise|hike|\$|€|£|money|cheap|worth"),
    ],
    "support": [
        ("no_response", (), r"no (response|reply|answer)|never (respond|repl|answer|got back|get back)|ignor|no one|nobody"
                            r"|didn'?t (respond|reply|get back)|still waiting"),
        ("unhelpful", (), r"useless|unhelpful|not help|didn'?t help|doesn'?t help|rude|\bbots?\b|automat|scripted|in circles"),
        ("contact", (), r"contact|reach|e-?mail|phone|\bcall\b|\bchat\b|live agent|human|real person"),
    ],
    "other": [
        ("update_regression", ("update",), r"updat|new version|latest version"),
    ],
}
_COMPILED = {t: [(theme, frozenset(ents), re.compile(rx)) for theme, ents, rx in rules]
             for t, rules in THEME_RULES.items()}

THEME_NAMES = {
    "access.account_security": ("Hacked or compromised accounts", "Unauthorized access, stolen or hijacked accounts."),
    "access.password_reset": ("Password reset and verification codes", "Password resets, verification codes and email links fail."),
    "access.third_party_login": ("Facebook/Google/Apple sign-in", "Problems signing in through third-party identity providers."),
    "access.signup": ("Sign-up and account creation", "Users cannot register or create an account."),
    "access.login": ("Login failures and forced logouts", "Users cannot log in, or are logged out."),
    "usability.ads": ("Ad interruptions", "Ad frequency, length or intrusiveness disrupts listening."),
    "usability.shuffle_queue": ("Shuffle, queue and skip behaviour", "Shuffle quality, queue management, repeat and skip controls."),
    "usability.playlist_library": ("Playlist and library management", "Managing playlists, liked songs and the library."),
    "usability.controls": ("Controls, widgets and notifications", "Buttons, lock-screen/notification controls and widgets."),
    "usability.ui_redesign": ("Layout and redesign complaints", "Home screen, layout and redesign changes users dislike."),
    "usability.navigation": ("Navigation and ease of use", "Hard-to-navigate or confusing app structure."),
    "playback.crash": ("Crashes and launch failures", "The app crashes, closes or will not open."),
    "playback.resources": ("Battery, storage and memory use", "Excessive battery, storage, memory or data use."),
    "playback.devices": ("Bluetooth, car and connected devices", "Playback on Bluetooth, car, Connect, watch and TV devices."),
    "playback.connection": ("Connection and network errors", "Playback fails with connection, network or server errors."),
    "playback.stops_pausing": ("Playback stops or pauses", "Music stops, pauses or cuts out, often in the background."),
    "playback.lag_loading": ("Lag, buffering and slow loading", "Slow loading, buffering, freezing or lag."),
    "playback.audio_quality": ("Audio quality and volume", "Sound quality, volume and equalizer problems."),
    "downloads.disappearing": ("Downloads disappear", "Downloaded music is deleted or must be re-downloaded."),
    "downloads.storage": ("Download storage and SD card", "Storage location, space and SD-card issues for downloads."),
    "downloads.offline_playback": ("Offline listening fails", "Downloaded music does not play offline."),
    "downloads.download_failure": ("Downloads fail or stall", "Songs will not download or downloads get stuck."),
    "catalog.lyrics": ("Lyrics availability", "Lyrics missing, paywalled or out of sync."),
    "catalog.podcasts_audiobooks": ("Podcasts and audiobooks", "Podcast and audiobook content or behaviour."),
    "catalog.missing_content": ("Missing or unavailable content", "Songs or artists missing, removed or region-locked."),
    "catalog.recommendations": ("Recommendations and discovery", "Repetitive or poor recommendations, radio and mixes."),
    "catalog.search": ("Search", "Search does not find the expected content."),
    "billing.charge_refund": ("Unexpected charges and refunds", "Unexpected or double charges, payments and refunds."),
    "billing.cancel_subscription": ("Cancelling a subscription", "Users cannot cancel or are charged after cancelling."),
    "billing.premium_entitlement": ("Premium not recognised", "Paid Premium (incl. Family/Duo/Student) not active or lost."),
    "billing.free_tier_limits": ("Free-tier restrictions and paywalls", "Features locked behind Premium on the free tier."),
    "billing.price": ("Price and value", "Subscription price, increases and value for money."),
    "support.no_response": ("Support does not respond", "Support never replies or ignores users."),
    "support.unhelpful": ("Unhelpful support", "Support answers are useless, scripted or automated."),
    "support.contact": ("Hard to contact support", "No easy way to reach a human."),
    "other.update_regression": ("Recent update made the app worse", "Generic complaints that an update broke or worsened the app."),
}


def classify_issue(record: dict, text: str) -> Tuple[str, str]:
    """Return ``(issue_id, rule)`` for one complaint/cancellation record. Deterministic, model-free."""
    topic = record.get("topic") if record.get("topic") in TOPICS else "other"
    ents = {e.strip().lower() for e in (record.get("entities") or []) if isinstance(e, str)}
    lowered = (text or "").lower()
    for theme, theme_ents, rx in _COMPILED.get(topic, []):
        if ents & theme_ents:
            return "%s.%s" % (topic, theme), "%s:entity" % THEME_RULES_VERSION
        if rx.search(lowered):
            return "%s.%s" % (topic, theme), "%s:text" % THEME_RULES_VERSION
    return "%s.general" % topic, "%s:fallback" % THEME_RULES_VERSION


def fallback_name(issue_id: str) -> Tuple[str, str]:
    if issue_id in THEME_NAMES:
        return THEME_NAMES[issue_id]
    topic = issue_id.split(".", 1)[0]
    return ("General %s complaints" % topic, "%s complaints that match no specific theme rule." % topic.capitalize())


def rule_text(issue_id: str) -> str:
    topic, _, theme = issue_id.partition(".")
    for t, ents, rx in THEME_RULES.get(topic, []):
        if t == theme:
            return "%s: entities %s or text /%s/" % (THEME_RULES_VERSION, list(ents), rx)
    return "%s: no theme rule matched (fallback)" % THEME_RULES_VERSION


def assign(records: Dict[str, dict], texts: Dict[str, str]) -> Dict[str, List[str]]:
    """issue_id -> review IDs in CSV order (texts order first, then any records not in texts)."""
    issues: Dict[str, List[str]] = {}
    order: Iterable[str] = list(texts.keys()) + [r for r in records if r not in texts]
    for rid in order:
        rec = records.get(rid)
        if not rec or rec.get("status") != "completed" or rec.get("intent") not in RANKED_INTENTS:
            continue
        iid, _ = classify_issue(rec, texts.get(rid, ""))
        issues.setdefault(iid, []).append(rid)
    return issues


def select_quotes(review_ids: List[str], records: Dict[str, dict], k: int, max_chars: int = 300) -> List[dict]:
    """Deterministic quote choice: prefer 20..max_chars-char quotes, then sha256(review_id); distinct texts."""
    ranked = []
    for rid in review_ids:
        q = (records.get(rid) or {}).get("evidence_quote")
        if isinstance(q, str) and q.strip():
            ranked.append((not (20 <= len(q) <= max_chars), sha256_hex(rid), rid, q))
    ranked.sort()
    out, seen = [], set()
    for _, _, rid, q in ranked:
        if q in seen:
            continue
        seen.add(q)
        out.append({"review_id": rid, "quote": q if len(q) <= max_chars else q[:max_chars] + "..."})
        if len(out) >= k:
            break
    return out


def build_evidence_pack(issues: Dict[str, List[str]], records: Dict[str, dict], max_issues: int,
                        quotes_per_issue: int, max_chars: int) -> dict:
    stats = []
    for iid, rids in issues.items():
        sev = sum(records[r]["severity"] for r in rids)
        stats.append((-len(rids), iid, rids, sev))
    stats.sort()
    pack = []
    for neg, iid, rids, sev in stats[:max_issues]:
        topic, _, theme = iid.partition(".")
        pack.append({"issue_id": iid, "topic": topic, "theme": theme, "complaint_count": -neg,
                     "severity_sum": sev, "mean_severity": mean_string(sev, -neg),
                     "quotes": select_quotes(rids, records, quotes_per_issue, max_chars)})
    return {"theme_rules_version": THEME_RULES_VERSION, "selection": "top %d issues by complaint_count, "
            "then issue_id; <= %d distinct evidence_quotes each, chosen by length band then sha256(review_id)"
            % (max_issues, quotes_per_issue), "issues": pack}


PROMPT = """You name customer-complaint issue clusters for a Spotify product team.
Each cluster was formed by deterministic keyword rules; you cannot change membership.
For every issue_id given, write a short name (<= 8 words) and a one-sentence description grounded
only in the quotes provided. Return ONLY JSON: {"issues": [{"issue_id": "...", "name": "...",
"description": "..."}]}. Use only the issue_ids given, each at most once. No markdown."""


def parse_names(text: str, allowed: List[str]) -> Tuple[Dict[str, dict], List[str]]:
    """Validate the model output. Returns (accepted {issue_id: {name, description}}, rejected notes)."""
    payload = parse_json_payload(text)
    items = payload.get("issues") if isinstance(payload, dict) else payload
    if isinstance(payload, dict) and items is None:
        items = [dict(v, issue_id=k) for k, v in payload.items() if isinstance(v, dict)]
    if not isinstance(items, list):
        raise ValueError("no issues list")
    allowed_set, accepted, rejected, seen = set(allowed), {}, [], set()
    for item in items:
        iid = item.get("issue_id") if isinstance(item, dict) else None
        if iid not in allowed_set:
            rejected.append("unknown issue_id %r" % (iid,))
            continue
        if iid in seen:
            rejected.append("duplicate issue_id %r" % iid)
            accepted.pop(iid, None)
            continue
        seen.add(iid)
        name, desc = item.get("name"), item.get("description")
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            rejected.append("bad name for %s" % iid)
            continue
        if not isinstance(desc, str) or len(desc) > 600:
            desc = ""
        accepted[iid] = {"name": name.strip(), "description": desc.strip()}
    return accepted, rejected


def run(ctx: StageContext) -> dict:
    cfg = ctx.config.get("group") or {}
    out = ctx.stage_dir(STAGE)
    issues = assign(ctx.records, ctx.texts)

    rows = [{"issue_id": iid, "review_id": rid} for iid in sorted(issues) for rid in issues[iid]]
    atomic_write_text(out / "membership.csv", _csv_text(("issue_id", "review_id"), rows))

    pack = build_evidence_pack(issues, ctx.records, int(cfg.get("max_issues", 30)),
                               int(cfg.get("quotes_per_issue", 5)), int(cfg.get("max_quote_chars", 300)))
    atomic_write_json(out / "evidence_pack.json", pack)
    pack_ids = [p["issue_id"] for p in pack["issues"]]
    sent_ids = []
    for p in pack["issues"]:
        for q in p["quotes"]:
            if q["review_id"] not in sent_ids:
                sent_ids.append(q["review_id"])
    max_tokens = int(cfg.get("max_tokens", 80 * max(1, len(pack_ids)) + 200))

    names: Dict[str, dict] = {}
    rejected: List[str] = []
    info: dict = {"cache_hit": False, "attempts": 0}
    if pack_ids and ctx.chat is not None:
        model = chat_model_name(ctx, STAGE)
        cache = StageCache(ctx, STAGE)
        payload = {"issues": [{"issue_id": p["issue_id"], "complaint_count": p["complaint_count"],
                               "quotes": [q["quote"] for q in p["quotes"]]} for p in pack["issues"]]}
        messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": dumps_line(payload)}]
        key = StageCache.key(STAGE, PROMPT, model, {"max_tokens": max_tokens, "temperature": 0.0}, payload)
        parsed, info = cached_chat(ctx, cache, role=STAGE, key=key, messages=messages, max_tokens=max_tokens,
                                   review_ids=sent_ids, response_format="json",
                                   validate=lambda t: parse_names(t, pack_ids), evidence_pack="group/evidence_pack.json")
        if parsed is not None:
            names, rejected = parsed
        cache.finish()

    out_issues = []
    for iid in sorted(issues, key=lambda i: (-len(issues[i]), i)):
        topic, _, theme = iid.partition(".")
        fb_name, fb_desc = fallback_name(iid)
        got = names.get(iid)
        out_issues.append({"issue_id": iid, "name": got["name"] if got else fb_name,
                           "description": (got["description"] or fb_desc) if got else fb_desc,
                           "topic": topic, "theme": theme, "rule": rule_text(iid),
                           "complaint_count": len(issues[iid]),
                           "name_source": "model" if got else "fallback"})
    atomic_write_json(out / "issues.json", out_issues)
    atomic_write_json(out / "naming_report.json", {"prompt_version": PROMPT_VERSION, "prompt_sha256": sha256_hex(PROMPT),
                                                   "named_by_model": sorted(names), "rejected": rejected,
                                                   "cache_hit": info.get("cache_hit"),
                                                   "request_id": info.get("request_id")})
    return {"issues": len(issues), "members": len(rows), "named_by_model": len(names),
            "rejected": len(rejected), "cache_hit": bool(info.get("cache_hit")), "calls": info.get("attempts", 0)}


def theme_table() -> Dict[str, List[str]]:
    """topic -> theme names in priority order (plus the general fallback)."""
    return {t: [r[0] for r in THEME_RULES.get(t, [])] + ["general"] for t in TOPICS}
