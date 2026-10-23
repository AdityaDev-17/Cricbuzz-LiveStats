"""Pure functions that convert raw Cricbuzz text/JSON into clean values."""

import re
from datetime import date

import pandas as pd

FORMAT_MAP = {"TEST": "Test", "ODI": "ODI", "T20": "T20I", "T20I": "T20I"}


def normalize_format(raw: str | None) -> str | None:
    """'T20' -> 'T20I', 'TEST' -> 'Test'. Returns None for unknown formats."""
    return FORMAT_MAP.get((raw or "").strip().upper())


def epoch_ms_to_date(ms: str | int | None) -> date | None:
    """'1792652400000' -> date in IST."""
    if not ms:
        return None
    return pd.to_datetime(int(ms), unit="ms", utc=True).tz_convert("Asia/Kolkata").date()


def parse_toss(text: str | None) -> tuple[str | None, str | None]:
    """'India opt to bowl' -> ('India', 'bowl')."""
    if not text:
        return None, None
    m = re.search(
        r"^(?P<team>.+?)\s+(?:won the toss and\s+)?(?:opt|opted|elect|elected|chose)\s+to\s+"
        r"(?P<decision>bat|bowl|field)",
        text.strip(),
        re.IGNORECASE,
    )
    if not m:
        return None, None
    decision = m["decision"].lower()
    return m["team"].strip(), "bowl" if decision == "field" else decision


def parse_result(text: str | None) -> dict:
    """'India won by 4 wkts' -> {'winner': 'India', 'margin': 4, 'type': 'wickets'}."""
    out = {"winner": None, "margin": None, "type": None}
    if not text:
        return out
    t = text.strip()

    m = re.search(r"^(?P<team>.+?)\s+won by an innings and (?P<m>\d+) runs?", t, re.I)
    if m:
        return {"winner": m["team"].strip(), "margin": int(m["m"]), "type": "innings"}

    m = re.search(r"^(?P<team>.+?)\s+won by (?P<m>\d+)\s*(?P<unit>runs?|wkts?|wickets?)", t, re.I)
    if m:
        unit = "runs" if m["unit"].lower().startswith("run") else "wickets"
        return {"winner": m["team"].strip(), "margin": int(m["m"]), "type": unit}

    low = t.lower()
    if "tied" in low:
        out["type"] = "tie"
    elif "drawn" in low or "draw" in low:
        out["type"] = "draw"
    elif "no result" in low or "abandon" in low:
        out["type"] = "no result"
    return out


def overs_to_balls(overs: str | float | None) -> int:
    """'3.4' -> 22, '4' -> 24."""
    if overs in (None, ""):
        return 0
    whole, _, part = str(overs).partition(".")
    return int(whole) * 6 + (int(part) if part else 0)


def parse_capacity(raw: str | int | None) -> int | None:
    """'20,000' -> 20000; missing/unparseable -> None."""
    if raw is None:
        return None
    m = re.search(r"\d[\d,]*", str(raw))
    return int(m.group().replace(",", "")) if m else None


def to_number(raw, kind=float):
    """'141.18' -> 141.18; '-', '', None -> None; '183*' -> 183."""
    if raw in (None, "", "-"):
        return None
    try:
        return kind(str(raw).replace("*", "").replace(",", "").strip())
    except ValueError:
        return None


def parse_dismissal(outdec: str | None) -> dict:
    """Return {'is_out', 'kind', 'fielder'} from text like 'c X b Y'."""
    text = (outdec or "").strip()
    if not text or text.lower().startswith(("not out", "retired hurt", "batting")):
        return {"is_out": False, "kind": None, "fielder": None}

    m = re.match(r"^c\s*&\s*b\s+(?P<bowler>.+)$", text, re.I)
    if m:
        return {"is_out": True, "kind": "catch", "fielder": m["bowler"].strip()}

    m = re.match(r"^c\s+(?:\(sub\)\s*)?(?P<f>.+?)\s+b\s+.+$", text, re.I)
    if m:
        return {"is_out": True, "kind": "catch", "fielder": m["f"].strip()}

    m = re.match(r"^st\s+(?P<f>.+?)\s+b\s+.+$", text, re.I)
    if m:
        return {"is_out": True, "kind": "stumping", "fielder": m["f"].strip()}

    m = re.match(r"^run out\s*\((?P<f>[^/)]+)", text, re.I)
    if m:
        return {"is_out": True, "kind": "run_out", "fielder": m["f"].strip()}

    return {"is_out": True, "kind": "other", "fielder": None}


def pivot_career_grid(data: dict) -> dict[str, dict[str, str]]:
    """Turn the headers x values grid into {'Test': {'Matches': '123', ...}, ...}.
    Keeps only Test / ODI / T20I columns."""
    headers = data.get("headers", [])
    result: dict[str, dict[str, str]] = {}
    for col_idx, header in enumerate(headers[1:], start=1):
        fmt = normalize_format(header)
        if not fmt:
            continue  # skips IPL etc.
        result[fmt] = {
            row["values"][0]: row["values"][col_idx]
            for row in data.get("values", [])
            if len(row.get("values", [])) > col_idx
        }
    return result
