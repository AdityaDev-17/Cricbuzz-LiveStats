"""Sanity-check every parser against the JSON saved in data/raw."""

import json
from pathlib import Path

from utils import parsers as p

RAW = Path("data/raw")
load = lambda name: json.loads((RAW / f"{name}.json").read_text(encoding="utf-8"))

print("=== Unit checks ===")
assert p.parse_toss("India opt to bowl") == ("India", "bowl")
assert p.parse_toss("Australia won the toss and elected to field") == ("Australia", "bowl")
assert p.parse_result("India won by 4 wkts") == {"winner": "India", "margin": 4, "type": "wickets"}
assert p.parse_result("England won by 35 runs")["type"] == "runs"
assert p.parse_result("India won by an innings and 32 runs")["type"] == "innings"
assert p.parse_result("Match tied")["type"] == "tie"
assert p.overs_to_balls("3.4") == 22 and p.overs_to_balls("4") == 24
assert p.parse_capacity("20,000") == 20000 and p.parse_capacity(None) is None
assert p.parse_dismissal("c Sanju Samson b Mayank Yadav")["fielder"] == "Sanju Samson"
assert p.parse_dismissal("c & b Kuldeep Yadav")["fielder"] == "Kuldeep Yadav"
assert p.parse_dismissal("st Dhoni b Jadeja")["kind"] == "stumping"
assert p.parse_dismissal("not out")["is_out"] is False
print("All unit checks passed.\n")

print("=== Real scorecard (match 161190) ===")
sc = load("match_161190_scorecard")
for inn in sc["scorecard"]:
    batted = [b for b in inn["batsman"] if b["balls"] > 0 or b["outdec"]]
    print(
        f"Innings {inn['inningsid']} - {inn['batteamname']}: "
        f"{len(batted)} batted / {len(inn['batsman'])} listed, {len(inn['bowler'])} bowlers"
    )
    for pos, b in enumerate(batted[:3], start=1):
        print(f"  #{pos} {b['name']}: {b['runs']}({b['balls']}) -> {p.parse_dismissal(b['outdec'])}")
    for bw in inn["bowler"][:2]:
        print(f"  BOWL {bw['name']}: overs={bw['overs']} -> balls={p.overs_to_balls(bw['overs'])}")
print("Result:", p.parse_result(sc["status"]))

print("\n=== Venue 371 ===")
v = load("venue_371")
print(v["ground"], v["city"], v["country"], p.parse_capacity(v.get("capacity")))

print("\n=== Career grid (player 1413) ===")
bat = load("player_1413_batting")
print("Raw headers:", bat["headers"])
print("Row labels:", [r["values"][0] for r in bat["values"]])
grid = p.pivot_career_grid(bat)
for fmt, stats in grid.items():
    print(fmt, {k: stats[k] for k in list(stats)[:6]})

bowl = load("player_1413_bowling")
print("\nBowling row labels:", [r["values"][0] for r in bowl["values"]])
