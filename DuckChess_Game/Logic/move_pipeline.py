from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple


@dataclass
class TurnResult:
    ok: bool
    captured_piece: Any = None
    error: Optional[str] = None


class MovePipeline:
    """
    Orchestrates a complete Duck Chess turn (piece move + duck placement) as a
    single validated operation.

    Uses only the public API of GameLogicMixin:
        get_piece_legal_moves(r, c), execute_move(start, end, animated),
        place_duck(pos, animated), and public attributes:
        board, turn, phase, duck_pos, prev_duck_pos.
    """

    def __init__(self, game_logic):
        self._g = game_logic

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def execute_full_turn(
        self,
        piece_start: Tuple[int, int],
        piece_end: Tuple[int, int],
        duck_dest: Tuple[int, int],
    ) -> TurnResult:
        """
        Validates then executes: piece_start→piece_end, then duck→duck_dest.

        Returns TurnResult(ok=True) on full success.
        Returns TurnResult(ok=False, error=...) when pre-validation fails
        (no state mutation occurs).
        Returns TurnResult(ok=False, error="ATOMIC_FAILURE: ...") when the piece
        move succeeded but duck placement subsequently failed — state is left in
        the 'move_duck' phase; the caller must resolve it.
        """
        g = self._g

        if g.phase != 'move_piece':
            return TurnResult(
                ok=False,
                error=f"Expected phase 'move_piece', got {g.phase!r}",
            )

        if not self.is_valid_piece_move(piece_start, piece_end):
            return TurnResult(
                ok=False,
                error=f"Illegal piece move: {piece_start} -> {piece_end}",
            )

        # Validate duck destination against the projected post-move board so
        # we can reject it before touching any state.
        if duck_dest in self._projected_duck_invalids(piece_start, piece_end):
            return TurnResult(
                ok=False,
                error=f"Invalid duck destination {duck_dest} after projected piece move",
            )

        # Pre-validation passed — mutation begins here.
        captured = g.board[piece_end[0]][piece_end[1]]
        g.execute_move(piece_start, piece_end, animated=False)

        # A king capture ends the game immediately; duck placement is moot.
        if g.phase != 'move_duck':
            return TurnResult(ok=True, captured_piece=captured)

        if not self.is_valid_duck_placement(duck_dest):
            return TurnResult(
                ok=False,
                captured_piece=captured,
                error=(
                    f"ATOMIC_FAILURE: piece move succeeded but duck destination "
                    f"{duck_dest} is invalid post-move. Phase is 'move_duck' and "
                    f"must be resolved by the caller."
                ),
            )

        phase_before = g.phase
        g.place_duck(duck_dest, animated=False)

        if g.phase == phase_before:
            return TurnResult(
                ok=False,
                captured_piece=captured,
                error=(
                    f"ATOMIC_FAILURE: place_duck silently no-op'd for {duck_dest}. "
                    f"Phase did not advance from 'move_duck'."
                ),
            )

        return TurnResult(ok=True, captured_piece=captured)

    def is_valid_piece_move(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
    ) -> bool:
        """True if end is in the legal destinations for the piece at start on the current turn."""
        g = self._g
        r, c = start
        cell = g.board[r][c]
        if cell is None or cell.color != g.turn:
            return False
        return end in g.get_piece_legal_moves(r, c)

    def is_valid_duck_placement(self, duck_dest: Tuple[int, int]) -> bool:
        """True if duck_dest is in-bounds, empty, and not the previous duck position."""
        g = self._g
        dr, dc = duck_dest
        if not (0 <= dr <= 7 and 0 <= dc <= 7):
            return False
        if g.board[dr][dc] is not None:
            return False
        prev = getattr(g, 'prev_duck_pos', (-1, -1))
        return duck_dest != prev

    def get_all_valid_turns(
        self,
    ) -> List[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]:
        """
        Enumerates every (piece_start, piece_end, duck_dest) triple legal in the
        current position without mutating game state.

        Duck destinations are projected per piece-move: the source square becomes
        available, the destination square becomes occupied.

        NOTE: O(pieces × moves × 64) — use for testing/analysis, not hot loops.
        """
        g = self._g
        results = []
        my_color = g.turn

        for r in range(8):
            for c in range(8):
                cell = g.board[r][c]
                if cell is None or cell.color != my_color:
                    continue
                for end in g.get_piece_legal_moves(r, c):
                    invalid_duck = self._projected_duck_invalids((r, c), end)
                    for dr in range(8):
                        for dc in range(8):
                            if (dr, dc) not in invalid_duck:
                                results.append(((r, c), end, (dr, dc)))

        return results

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _projected_duck_invalids(
        self,
        piece_start: Tuple[int, int],
        piece_end: Tuple[int, int],
    ):
        """
        Returns the set of squares that will be unavailable for the duck AFTER
        piece_start moves to piece_end: all currently occupied squares adjusted
        for the move, plus prev_duck_pos.
        """
        g = self._g
        invalid = set()

        for r in range(8):
            for c in range(8):
                if g.board[r][c] is not None:
                    invalid.add((r, c))

        invalid.discard(piece_start)
        invalid.add(piece_end)

        prev = getattr(g, 'prev_duck_pos', (-1, -1))
        if prev != (-1, -1):
            invalid.add(prev)

        return invalid
