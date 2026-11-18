"""Five Claude Haikus voting vs one Claude Opus: chess, no tools, no code.

Usage: python match.py <game name> <white> <black> <out dir>
  side = opus | haiku | team   (team = 5 independent Claude Haiku 5.5 calls, majority vote)
Each turn every voter gets the same prompt as in ep07: move list, FEN and a text diagram.
Each call is `claude -p` with every tool disabled, a fresh session, no settings or MCP.
Team vote: the 5 Haikus answer independently (none sees another's answer). Illegal answers are dropped;
the legal move with the most votes is played; a tie goes to the tied move named by the lowest-numbered Haiku.
If no answer is legal, the side is asked again with its illegal tries listed (as in ep07);
3 rounds with no legal move = forfeit. A single model gets the same 3 tries.
python-chess is the referee. A game still running at move 150 is scored a draw.
Every call and reply is logged to <out dir>/<game>.jsonl; the PGN to <game>.pgn.
"""
import json, re, subprocess, sys, time, pathlib, datetime
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import chess, chess.pgn

game, white, black, out = sys.argv[1], sys.argv[2], sys.argv[3], pathlib.Path(sys.argv[4])
out.mkdir(parents=True, exist_ok=True)
LOG = open(out / f"{game}.jsonl", "a")
MODEL = {"opus": "claude-opus-5-5", "haiku": "claude-haiku-5-5", "team": "claude-haiku-5-5"}
NAME = {"opus": "OPUS 5.5", "haiku": "HAIKU 5.5", "team": "5 HAIKUS"}
COL = {"opus": "\033[38;5;117m", "haiku": "\033[38;5;150m", "team": "\033[38;5;150m"}
B, R, D, X = "\033[1m", "\033[31m", "\033[2m", "\033[0m"


def system(side):
    return (f"You are playing a game of chess as {side} against another AI. You have no tools and no code. "
            "Reply in exactly two lines: line 1, a short comment on your move under 12 words; line 2, only your move in SAN.")


def log(**kw):
    kw["t"] = datetime.datetime.now().isoformat(timespec="seconds"); LOG.write(json.dumps(kw) + "\n"); LOG.flush()


def movelist(board):
    b = chess.Board(); parts = []
    for i, m in enumerate(board.move_stack):
        if i % 2 == 0: parts.append(f"{i // 2 + 1}.")
        parts.append(b.san(m)); b.push(m)
    return " ".join(parts) or "(none, game start)"


def ask(model, board, misses, voter=0):
    side = "White" if board.turn == chess.WHITE else "Black"
    p = (f"Moves so far: {movelist(board)}\nPosition (FEN): {board.fen()}\n"
         f"Board (White at the bottom, uppercase = White):\n{board}\n")
    for m in misses:
        p += f"You tried {m}, which is not a legal move in this position.\n"
    p += f"You are {side}. Your move."
    t0 = time.time()
    r = subprocess.run(["claude", "-p", "--model", model, "--tools", "", "--no-session-persistence",
                        "--setting-sources", "", "--strict-mcp-config", "--output-format", "json",
                        "--system-prompt", system(side), p], capture_output=True, text=True, timeout=900)
    try:
        j = json.loads(r.stdout); text = j.get("result", ""); used = ",".join(j.get("modelUsage", {}).keys())
    except json.JSONDecodeError:
        text, used = r.stdout + r.stderr, "?"
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    comment = lines[0] if len(lines) > 1 else ""
    raw = lines[-1] if lines else ""
    san = re.sub(r"^\d+\.(\.\.)?\s*", "", raw).strip(" .*`")
    secs = round(time.time() - t0, 1)
    log(ply=board.ply(), side=side, model=model, voter=voter, prompt=p, reply=text, used=used, secs=secs)
    return comment, san, secs


def legal(board, san):
    try:
        return board.parse_san(san)
    except ValueError:
        return None


def show(board):
    rows = str(board.unicode(invert_color=True, empty_square="·")).splitlines()
    print()
    for i, row in enumerate(rows):
        print(f"   {D}{8 - i}{X}  " + " ".join(row.split()))
    print(f"      {D}a b c d e f g h{X}\n")


def turn(who, board, misses):
    """returns (move or None, comment, secs, ballot text, bad answers)"""
    if who != "team":
        comment, san, secs = ask(MODEL[who], board, misses)
        mv = legal(board, san)
        return mv, comment, secs, "", ([] if mv else [san])
    t0 = time.time()
    with ThreadPoolExecutor(5) as ex:
        ans = list(ex.map(lambda v: ask(MODEL[who], board, misses, v), range(1, 6)))
    votes = [(i, legal(board, san), c) for i, (c, san, _) in enumerate(ans, 1)]
    good = [(i, m, c) for i, m, c in votes if m]
    bad = [ans[i - 1][1] or "(no move)" for i, m, _ in votes if not m]
    if not good:
        return None, "", round(time.time() - t0, 1), "", bad
    count = Counter(m for _, m, _ in good)
    top = max(count.values())
    pick_i, pick, pick_c = next((i, m, c) for i, m, c in good if count[m] == top)
    tally = ", ".join(f"{board.san(m)} x{n}" for m, n in count.most_common())
    if bad:
        tally += f", illegal x{len(bad)}"
    log(ply=board.ply(), vote={board.san(m): n for m, n in count.items()}, bad=bad, pick=pick.uci(), by=pick_i)
    return pick, pick_c, round(time.time() - t0, 1), tally, bad


board = chess.Board(); illegal = {"w": 0, "b": 0}; result = None; forfeit = None
print(f"{B}{COL[white]}{NAME[white]}{X}{B} (White) vs {COL[black]}{NAME[black]}{X}{B} (Black){X}")
print(f"{D}no tools, no code, team = 5 Haikus answer alone, majority vote, 3 illegal rounds = forfeit{X}")
show(board)
while not board.is_game_over(claim_draw=True) and board.fullmove_number <= 150:
    n = board.fullmove_number
    key = "w" if board.turn == chess.WHITE else "b"
    who = white if board.turn == chess.WHITE else black
    dots = "." if board.turn == chess.WHITE else "..."
    misses = []; rounds = 0
    while True:
        mv, comment, secs, tally, bad = turn(who, board, misses)
        illegal[key] += len(bad)
        if mv:
            break
        rounds += 1; misses.extend(b for b in bad if b not in misses)
        print(f" {R}{B}ILLEGAL{X}  {COL[who]}{NAME[who]}{X} {n}{dots} {' / '.join(bad)}   {D}round {rounds}/3{X}")
        log(ply=board.ply(), side=who, illegal=bad, tries=rounds)
        if rounds == 3:
            forfeit = who; break
    if forfeit:
        result = "0-1" if forfeit == white else "1-0"
        print(f"\n {R}{B}THREE ILLEGAL ROUNDS. {NAME[forfeit]} FORFEIT.{X}"); break
    extra = f"   {D}votes: {tally}{X}" if tally else ""
    print(f" {COL[who]}{B}{NAME[who]}{X}  {n}{dots} {board.san(mv)}   {D}{secs}s{X}   \"{comment}\"{extra}")
    board.push(mv); log(ply=board.ply(), move=mv.uci(), fen=board.fen())
    if board.ply() % 2 == 0 or board.is_game_over(): show(board)
if result is None:
    result = board.result(claim_draw=True) if board.is_game_over(claim_draw=True) else "1/2-1/2"
outcome = board.outcome(claim_draw=True)
why = f"FORFEIT ({NAME[forfeit]}, 3 illegal rounds)" if forfeit else (outcome.termination.name if outcome else "MOVE 150 CAP")
print(f"\n {B}RESULT {result}{X}  {why}   moves: {board.fullmove_number}   "
      f"illegal answers: {NAME[white]} {illegal['w']}, {NAME[black]} {illegal['b']}")
log(result=result, why=why, illegal=illegal, moves=board.fullmove_number, white=white, black=black)
pg = chess.pgn.Game.from_board(board)
pg.headers.update({"Event": "5 Claude Haikus (vote) vs Claude Opus 5.5 (no tools)", "White": NAME[white],
                   "Black": NAME[black], "Result": result})
(out / f"{game}.pgn").write_text(str(pg) + "\n")
