# 5 Claude Haikus (voting) vs 1 Claude Opus: chess, no tools

Three games, 2026-11-19. Each move is a fresh `claude -p --tools ""` call. The team is five independent Claude Haiku 5.5 calls per move; the most-voted legal move is played, ties go to the lowest-numbered Haiku. Opus 5.5 won all three.

- `index.html`: every move, every vote, Stockfish loss per move (live at https://denzil10.github.io/haikus-vs-opus-chess/)
- `match.py`: referee (python-chess); `analyze.py`: Stockfish review; `replay.py`: the sped-up referee screen used in the video
- `games/`: full logs (every prompt and reply), PGNs, reviews
