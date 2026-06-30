from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from DuckChess_Game.Logic.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING


# Result of a validation: ok flag plus hard errors (issues) and soft notes (warnings)
@dataclass
class ValidationReport:
    ok: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class GameStateValidator:
    """
    Stateless diagnostic module. Never mutates state, never raises exceptions.
    All public methods return a ValidationReport.
    Consumes only the public API of the Logic layer.
    """

    VALID_PIECE_TYPES = {PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING}
    VALID_COLORS = {'w', 'b'}
    VALID_PHASES = {'move_piece', 'move_duck'}

    def validate_board_sync(
        self,
        board_2d: list,
        bb_mgr,
        duck_pos: Tuple[int, int],
    ) -> ValidationReport:
        """
        Verifies that every square in the 2D board agrees with the corresponding
        piece bitboard, and that the duck bitboard matches duck_pos.
        """
        issues: List[str] = []
        warnings: List[str] = []
        try:
            # Walk every square and compare the 2D board against the bitboards
            for r in range(8):
                for c in range(8):
                    sq = r * 8 + c  # 0..63 bit index for this square
                    cell = board_2d[r][c]

                    # For each piece type, the bit must be set iff the 2D cell holds it
                    for color in ('w', 'b'):
                        for p_type in self.VALID_PIECE_TYPES:
                            try:
                                bb_val = bb_mgr.piece_boards[color][p_type]
                                bb_has = bool(bb_val & (1 << sq))
                                board_has = (
                                    cell is not None
                                    and cell.color == color
                                    and cell.type == p_type
                                )
                                # Disagreement between the two representations is a sync error
                                if bb_has != board_has:
                                    issues.append(
                                        f"Piece sync mismatch at ({r},{c}) for "
                                        f"{color}{p_type}: bb={bb_has} board={board_has}"
                                    )
                            except Exception as e:
                                issues.append(
                                    f"Exception checking ({r},{c}) {color}{p_type}: {e}"
                                )

                    # The duck bitboard bit must match duck_pos for this square
                    try:
                        bb_duck = bool(bb_mgr.duck_board & (1 << sq))
                        pos_duck = (duck_pos == (r, c))
                        if bb_duck != pos_duck:
                            issues.append(
                                f"Duck sync mismatch at ({r},{c}): "
                                f"bb={bb_duck} duck_pos={pos_duck}"
                            )
                    except Exception as e:
                        issues.append(f"Exception checking duck at ({r},{c}): {e}")

        except Exception as e:
            issues.append(f"Unexpected error in validate_board_sync: {e}")

        return ValidationReport(ok=(len(issues) == 0), issues=issues, warnings=warnings)

    def validate_phase_consistency(
        self,
        phase: str,
        turn: str,
        duck_pos: Tuple[int, int],
        prev_duck_pos: Tuple[int, int],
    ) -> ValidationReport:
        """
        Checks that phase, turn, duck_pos, and prev_duck_pos are internally consistent.
        """
        issues: List[str] = []
        warnings: List[str] = []
        try:
            # Phase must be one of the two turn sub-phases
            if phase not in self.VALID_PHASES:
                issues.append(f"Invalid phase: {phase!r}")

            if turn not in self.VALID_COLORS:
                issues.append(f"Invalid turn: {turn!r}")

            # (-1, -1) means "duck not placed yet"; otherwise it must be on the board
            for name, pos in [("duck_pos", duck_pos), ("prev_duck_pos", prev_duck_pos)]:
                if pos == (-1, -1):
                    continue
                if (
                    not isinstance(pos, (tuple, list))
                    or len(pos) != 2
                    or not (0 <= pos[0] <= 7)
                    or not (0 <= pos[1] <= 7)
                ):
                    issues.append(f"{name} out of bounds: {pos}")

            # The duck must move each turn, so it can't stay on its previous square
            if duck_pos != (-1, -1) and duck_pos == prev_duck_pos:
                warnings.append(
                    "duck_pos == prev_duck_pos: duck has not moved from previous position"
                )

        except Exception as e:
            issues.append(f"Unexpected error in validate_phase_consistency: {e}")

        return ValidationReport(ok=(len(issues) == 0), issues=issues, warnings=warnings)

    def validate_en_passant(
        self,
        en_passant_target: Optional[Tuple[int, int]],
        board: list,
    ) -> ValidationReport:
        """
        Validates that en_passant_target is on a reachable row and that
        a pawn capable of capturing actually exists adjacent to it.
        """
        issues: List[str] = []
        warnings: List[str] = []
        try:
            if en_passant_target is None:
                return ValidationReport(ok=True)

            er, ec = en_passant_target

            if not (0 <= er <= 7 and 0 <= ec <= 7):
                issues.append(f"en_passant_target {en_passant_target} out of bounds")
                return ValidationReport(ok=False, issues=issues, warnings=warnings)

            # EP rows: row 5 (white just double-pushed, black captures) or
            #          row 2 (black just double-pushed, white captures)
            if er not in (2, 5):
                issues.append(
                    f"en_passant_target row {er} is not a valid EP row (expected 2 or 5)"
                )

            # Look for a pawn of the capturing color directly left/right of the target
            capturing_color = 'w' if er == 5 else 'b'
            found_pawn = False
            for dc in (-1, 1):
                nc = ec + dc
                if 0 <= nc <= 7:
                    cell = board[er][nc]
                    if cell and cell.type == PAWN and cell.color == capturing_color:
                        found_pawn = True
                        break

            # Absent pawn is a warning, not an issue: a stale EP target with no
            # capturing pawn is harmless — move gen will ignore it naturally.
            if not found_pawn:
                warnings.append(
                    f"No {capturing_color} pawn adjacent to en_passant_target "
                    f"{en_passant_target} that could capture"
                )

        except Exception as e:
            issues.append(f"Unexpected error in validate_en_passant: {e}")

        return ValidationReport(ok=(len(issues) == 0), issues=issues, warnings=warnings)

    def full_check(self, game_logic_instance) -> ValidationReport:
        """
        Runs all validators against a live GameLogicMixin instance.
        Reads only public attributes.
        """
        all_issues: List[str] = []
        all_warnings: List[str] = []

        try:
            board = game_logic_instance.board
            bb_mgr = game_logic_instance.bb_mgr
            duck_pos = game_logic_instance.duck_pos
            prev_duck_pos = getattr(game_logic_instance, 'prev_duck_pos', (-1, -1))
            phase = getattr(game_logic_instance, 'phase', 'move_piece')
            turn = game_logic_instance.turn
            ep = getattr(game_logic_instance, 'en_passant_target', None)

            # Run every validator and merge their issues/warnings into one report
            for report in (
                self.validate_board_sync(board, bb_mgr, duck_pos),
                self.validate_phase_consistency(phase, turn, duck_pos, prev_duck_pos),
                self.validate_en_passant(ep, board),
            ):
                all_issues.extend(report.issues)
                all_warnings.extend(report.warnings)

        except Exception as e:
            all_issues.append(f"full_check failed with unexpected error: {e}")

        return ValidationReport(
            ok=(len(all_issues) == 0),
            issues=all_issues,
            warnings=all_warnings,
        )
