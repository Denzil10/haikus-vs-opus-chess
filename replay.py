"""Replay a finished match.py game on the referee screen, from its log, faster than it was played.
  python replay.py <game.jsonl> [seconds per ply, default 0.35] [first ply to show, default 0]
Same facts match.py printed live (moves, think time, each side's comment, the team's vote count), laid out
for a 1080px-wide vertical terminal: the vote tally on its own line. Plies before <first ply> are applied silently.
A banner says it is a sped-up replay of the log. Recorded with vhs for the video.
"""
import json, sys, time
import chess

B, R, D, X = "\033[1m", "\033[31m", "\033[2m", "\033[0m"
NAME = {"opus": "OPUS 5.5", "haiku": "HAIKU 5.5", "team": "5 HAIKUS"}
COL = {"opus": "\033[38;5;117m", "haiku": "\033[38;5;150m", "team": "\033[38;5;150m"}
Y = "\033[38;5;221m"
rows = [json.loads(l) for l in open(sys.argv[1])]
step = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
first = int(sys.argv[3]) if len(sys.argv) > 3 else 0
res = rows[-1]
white, black = res["white"], res["black"]


def show(board):
    print()
    for i, row in enumerate(str(board.unicode(invert_color=True, empty_square="·")).splitlines()):
        print(f"   {D}{8 - i}{X}  " + " ".join(row.split()))
    print(f"      {D}a b c d e f g h{X}\n")


def out(*a, **k):
    if board.ply() >= first:
        print(*a, **k)


print(f"{B}{COL[white]}{NAME[white]}{X}{B} (White) vs {COL[black]}{NAME[black]}{X}{B} (Black){X}")
print(f"{D}no tools, no code · team: 5 Haikus answer alone, most votes plays{X}")
print(f"{D}replay of the real game log, sped up{X}")
board = chess.Board()
if first == 0:
    show(board); time.sleep(1.0)
replies, vote = [], None
for r in rows:
    if "result" in r:
        ill = r["illegal"]
        print(f"\n {B}RESULT {r['result']}{X}  {r['why']}  · moves: {r['moves']}")
    elif "reply" in r:
        replies.append(r)
    elif "vote" in r:
        vote = r
    elif "illegal" in r:
        out(f" {R}{B}ILLEGAL{X}  {COL[r['side']]}{NAME[r['side']]}{X}  {' / '.join(r['illegal'])}")
        if board.ply() >= first: time.sleep(step * 2)
        replies = []
    elif "move" in r:
        who = white if board.turn else black
        mv = chess.Move.from_uci(r["move"]); n = board.fullmove_number; dots = "." if board.turn else "..."
        if who == "team":
            pick = next(x for x in replies if x.get("voter") == vote["by"])
            secs = max(x["secs"] for x in replies)
            tally = " · ".join(f"{m} {c}" for m, c in sorted(vote["vote"].items(), key=lambda kv: -kv[1]))
            if vote["bad"]:
                tally += f" · {R}illegal {len(vote['bad'])}{X}"
        else:
            pick, secs, tally = replies[-1], replies[-1]["secs"], ""
        lines = [l.strip() for l in pick["reply"].strip().splitlines() if l.strip()]
        comment = lines[0] if len(lines) > 1 else ""
        out(f" {COL[who]}{B}{NAME[who]}{X}  {B}{n}{dots} {board.san(mv)}{X}   {D}{secs}s{X}")
        if tally:
            out(f"   {Y}votes{X}  {tally}")
        out(f"   {D}\"{comment}\"{X}")
        board.push(mv); replies, vote = [], None
        if board.ply() > first and (board.ply() % 2 == 0 or board.is_game_over()):
            show(board)
        if board.ply() > first:
            time.sleep(step)
time.sleep(4)
