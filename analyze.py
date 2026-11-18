"""Stockfish review of a finished game: centipawn loss per move, per side, and the worst blunders.
  python analyze.py <game.pgn> [depth=18]   -> prints a summary, writes <game>.eval.json beside the PGN
eval.json: per ply {ply, side, san, cp_before, cp_after, loss} (cp from White's view, mate = +-10000 clipped to 1000 for loss).
"""
import json, sys, pathlib
import chess, chess.engine, chess.pgn

pgn = pathlib.Path(sys.argv[1]); depth = int(sys.argv[2]) if len(sys.argv) > 2 else 18
g = chess.pgn.read_game(open(pgn))
eng = chess.engine.SimpleEngine.popen_uci("/opt/homebrew/bin/stockfish")
eng.configure({"Threads": 4, "Hash": 256})
lim = chess.engine.Limit(depth=depth)


def cp(board):
    return eng.analyse(board, lim)["score"].white().score(mate_score=10000)


b = g.board(); rows = []; before = cp(b)
for k, mv in enumerate(g.mainline_moves(), 1):
    side = "White" if b.turn else "Black"; san = b.san(mv); b.push(mv)
    after = cp(b)
    c0, c1 = max(-1000, min(1000, before)), max(-1000, min(1000, after))
    loss = max(0, (c0 - c1) if side == "White" else (c1 - c0))
    rows.append(dict(ply=k, side=side, move=(k + 1) // 2, san=san, cp_before=before, cp_after=after, loss=loss))
    before = after
eng.quit()
(pgn.with_suffix(".eval.json")).write_text(json.dumps(rows, indent=0))
print(g.headers["White"], "vs", g.headers["Black"], g.headers["Result"])
for side in ("White", "Black"):
    r = [x for x in rows if x["side"] == side]
    acpl = sum(x["loss"] for x in r) / max(1, len(r))
    bl = [x for x in r if x["loss"] >= 300]
    print(f"{side} {g.headers[side]}: {len(r)} moves, avg cp loss {acpl:.0f}, blunders(>=300) {len(bl)}")
    for x in sorted(r, key=lambda x: -x["loss"])[:4]:
        print(f"   {x['move']}{'.' if side == 'White' else '...'}{x['san']}  loss {x['loss']}  ({x['cp_before']} -> {x['cp_after']})")
