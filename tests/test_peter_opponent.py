"""Tests for PeterOpponent — the binary (offline Rust engine) opponent path.

PeterOpponent.predict() shells out to a local executable and parses its
stdout. The subprocess call is mocked so these tests stay hermetic: they
verify the command we build, the move-string parsing, the algebraic->coords
conversion, and the piece/duck action split (piece returned now, duck cached
for the next step).
"""
import subprocess
from types import SimpleNamespace
from unittest import mock

import pytest

from DuckChess_Game.Logic.peter_opponent import PeterOpponent
from DuckChess_Game.Logic.action_masker import ActionMasker


BINARY = "/fake/peter_engine"


def make_engine(turn="w", duck_pos=(-1, -1), fen="FAKEFEN"):
    """Minimal stand-in for the env engine PeterOpponent.predict() consumes.

    predict() only touches engine.turn, engine.duck_pos and
    engine.bb_mgr.generate_fen(turn, duck_pos).
    """
    bb_mgr = SimpleNamespace(generate_fen=mock.Mock(return_value=fen))
    return SimpleNamespace(turn=turn, duck_pos=duck_pos, bb_mgr=bb_mgr)


def completed(stdout):
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


@pytest.fixture
def masker():
    return ActionMasker()


class TestPredictParsing:
    def test_returns_encoded_piece_move_and_none(self, masker):
        """`e2e4@g5` -> piece move e2->e4 encoded; second element is None."""
        engine = make_engine()
        with mock.patch.object(subprocess, "run", return_value=completed("e2e4@g5")):
            opp = PeterOpponent(BINARY)
            action, second = opp.predict(engine)

        # to_coords: 'e2' -> (rank-1, file) = (1, 4); 'e4' -> (3, 4)
        assert action == masker.encode_move((1, 4), (3, 4))
        assert second is None

    def test_duck_action_is_cached_not_returned(self, masker):
        """The duck placement is stashed on the opponent for the next step."""
        engine = make_engine(duck_pos=(2, 2))
        with mock.patch.object(subprocess, "run", return_value=completed("e2e4@g5")):
            opp = PeterOpponent(BINARY)
            opp.predict(engine)

        # 'g5' -> (rank-1, file) = (4, 6); cached from current duck_pos (2,2)
        assert opp.cached_duck_action == masker.encode_move((2, 2), (4, 6))

    def test_duck_cached_from_sentinel_start_position(self, masker):
        """At game start duck_pos is (-1,-1); encode_move maps that to (0,0)."""
        engine = make_engine(duck_pos=(-1, -1))
        with mock.patch.object(subprocess, "run", return_value=completed("a1a2@h8")):
            opp = PeterOpponent(BINARY)
            opp.predict(engine)

        assert opp.cached_duck_action == masker.encode_move((-1, -1), (7, 7))
        assert opp.cached_duck_action == masker.encode_move((0, 0), (7, 7))

    def test_move_extracted_from_noisy_stdout(self, masker):
        """The regex finds the move embedded in surrounding engine log text."""
        engine = make_engine()
        noisy = "info depth 12 nodes 5000\nbestmove e2e4@g5\nreadyok\n"
        with mock.patch.object(subprocess, "run", return_value=completed(noisy)):
            opp = PeterOpponent(BINARY)
            action, _ = opp.predict(engine)
        assert action == masker.encode_move((1, 4), (3, 4))

    def test_all_corners_roundtrip(self, masker):
        """Each algebraic square parses to the (rank-1, file) coordinate."""
        cases = {
            "a1": (0, 0),
            "h1": (0, 7),
            "a8": (7, 0),
            "h8": (7, 7),
            "e4": (3, 4),
        }
        for note, expected in cases.items():
            engine = make_engine()
            stdout = f"{note}{note}@a1"  # start==end is fine for parsing
            with mock.patch.object(subprocess, "run", return_value=completed(stdout)):
                opp = PeterOpponent(BINARY)
                action, _ = opp.predict(engine)
            assert action == masker.encode_move(expected, expected)


class TestPredictFallback:
    def test_no_match_returns_zero(self):
        engine = make_engine()
        with mock.patch.object(subprocess, "run", return_value=completed("garbage output")):
            opp = PeterOpponent(BINARY)
            result = opp.predict(engine)
        assert result == 0

    def test_no_match_leaves_duck_action_unset(self):
        engine = make_engine()
        with mock.patch.object(subprocess, "run", return_value=completed("no move here")):
            opp = PeterOpponent(BINARY)
            opp.predict(engine)
        assert opp.cached_duck_action is None

    def test_empty_stdout_returns_zero(self):
        engine = make_engine()
        with mock.patch.object(subprocess, "run", return_value=completed("")):
            opp = PeterOpponent(BINARY)
            assert opp.predict(engine) == 0


class TestSubprocessCommand:
    def test_command_uses_fen_and_node_budget(self):
        engine = make_engine(turn="b", duck_pos=(3, 3), fen="rnbq/FEN w - -")
        with mock.patch.object(subprocess, "run", return_value=completed("e2e4@g5")) as run:
            opp = PeterOpponent(BINARY)
            opp.predict(engine)

        engine.bb_mgr.generate_fen.assert_called_once_with("b", (3, 3))
        cmd = run.call_args.args[0]
        assert cmd == [BINARY, "search", "rnbq/FEN w - -", "--nodes", "5000"]
        assert run.call_args.kwargs.get("capture_output") is True
        assert run.call_args.kwargs.get("text") is True


class TestConstruction:
    def test_each_opponent_owns_its_masker(self):
        a = PeterOpponent(BINARY)
        b = PeterOpponent(BINARY)
        assert isinstance(a._masker, ActionMasker)
        assert a._masker is not b._masker

    def test_initial_cached_duck_is_none(self):
        assert PeterOpponent(BINARY).cached_duck_action is None
