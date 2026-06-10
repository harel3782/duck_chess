"""Tests for PeterSiteConnector's pure translation layer.

The connector's __init__ launches a real Chromium via Playwright, so these
tests bypass it with object.__new__ and exercise only the stateless helpers:
the model<->algebraic coordinate flip, the 4096-action encoding (which must
agree with ActionMasker), pixel<->square mapping under both orientations, and
the SVG fill/path parsers used to scrape Peter's suggestions.
"""
import pytest

from DuckChess_Game.playwright_game.New.peter_interface import PeterSiteConnector
from DuckChess_Game.Logic.action_masker import ActionMasker


def make_connector(flipped=False):
    """Build a connector WITHOUT running __init__ (no browser launch).

    Only self.flipped is read by the helpers under test; everything else
    (browser, page, square_map) is irrelevant here.
    """
    conn = object.__new__(PeterSiteConnector)
    conn.flipped = flipped
    return conn


@pytest.fixture
def conn():
    return make_connector(flipped=False)


@pytest.fixture
def masker():
    return ActionMasker()


# ------------------------------------------------------------------ #
# Model coords <-> algebraic (orientation-independent vertical flip)   #
# ------------------------------------------------------------------ #

class TestCoordsAlgebraic:
    @pytest.mark.parametrize("rc,alg", [
        ((7, 4), "e1"),   # White king square
        ((0, 4), "e8"),   # Black king square
        ((0, 0), "a8"),
        ((7, 7), "h1"),
        ((7, 0), "a1"),
        ((0, 7), "h8"),
    ])
    def test_coords_to_algebraic(self, conn, rc, alg):
        assert conn.coords_to_algebraic(*rc) == alg

    @pytest.mark.parametrize("alg,rc", [
        ("e1", (7, 4)),
        ("e8", (0, 4)),
        ("a8", (0, 0)),
        ("h1", (7, 7)),
    ])
    def test_algebraic_to_coords(self, conn, alg, rc):
        assert conn.algebraic_to_coords(alg) == rc

    def test_roundtrip_all_squares(self, conn):
        for r in range(8):
            for c in range(8):
                alg = conn.coords_to_algebraic(r, c)
                assert conn.algebraic_to_coords(alg) == (r, c)

    def test_flip_is_independent_of_orientation(self):
        """coords_to_algebraic ignores the board's flip state by design."""
        a = make_connector(flipped=False).coords_to_algebraic(3, 5)
        b = make_connector(flipped=True).coords_to_algebraic(3, 5)
        assert a == b


# ------------------------------------------------------------------ #
# 4096-action encoding — must match ActionMasker                       #
# ------------------------------------------------------------------ #

class TestEncodeActionIndex:
    def test_matches_action_masker_for_e2e4(self, conn, masker):
        idx = conn.encode_to_action_index("e2", "e4")
        # e2->(6,4), e4->(4,4) after the vertical flip
        assert idx == masker.encode_move((6, 4), (4, 4))
        assert idx == 3364

    def test_in_valid_range(self, conn):
        assert 0 <= conn.encode_to_action_index("a1", "h8") < 4096

    def test_agrees_with_masker_over_all_squares(self, conn, masker):
        files = "abcdefgh"
        for sr in range(8):
            for sc in range(8):
                for er in range(8):
                    for ec in range(8):
                        start = conn.coords_to_algebraic(sr, sc)
                        end = conn.coords_to_algebraic(er, ec)
                        idx = conn.encode_to_action_index(start, end)
                        assert idx == masker.encode_move((sr, sc), (er, ec))

    def test_decodes_back_through_masker(self, conn, masker):
        idx = conn.encode_to_action_index("d2", "d4")
        start, end = masker.decode_move(idx)
        assert conn.coords_to_algebraic(*start) == "d2"
        assert conn.coords_to_algebraic(*end) == "d4"


# ------------------------------------------------------------------ #
# Pixel <-> square mapping under both orientations                     #
# ------------------------------------------------------------------ #

class TestPixelMapping:
    def test_not_flipped_top_left_is_a8(self, conn):
        assert conn.pixels_to_algebraic(0, 0) == "a8"

    def test_not_flipped_bottom_right_is_h1(self, conn):
        assert conn.pixels_to_algebraic(399, 399) == "h1"

    def test_not_flipped_center_square(self, conn):
        # x=200 -> col 4 (file e), y=200 -> row 4 -> rank 8-4-... = rank 4
        assert conn.pixels_to_algebraic(200, 200) == "e4"

    def test_flipped_top_left_is_h1(self):
        c = make_connector(flipped=True)
        assert c.pixels_to_algebraic(0, 0) == "h1"

    def test_flipped_bottom_right_is_a8(self):
        c = make_connector(flipped=True)
        assert c.pixels_to_algebraic(399, 399) == "a8"

    def test_pixel_to_file_rank_not_flipped(self, conn):
        assert conn.pixel_to_file_rank(0, 0) == (0, 7)      # a-file, rank 8
        assert conn.pixel_to_file_rank(399, 399) == (7, 0)  # h-file, rank 1

    def test_pixel_to_file_rank_flipped(self):
        c = make_connector(flipped=True)
        assert c.pixel_to_file_rank(0, 0) == (7, 0)         # h-file, rank 1
        assert c.pixel_to_file_rank(399, 399) == (0, 7)     # a-file, rank 8

    def test_orientation_mirrors_both_axes(self):
        """A given pixel maps to opposite squares depending on flip state."""
        unflipped = make_connector(flipped=False).pixels_to_algebraic(0, 0)
        flipped = make_connector(flipped=True).pixels_to_algebraic(0, 0)
        assert unflipped == "a8"
        assert flipped == "h1"


# ------------------------------------------------------------------ #
# SVG scraping helpers                                                 #
# ------------------------------------------------------------------ #

class TestExtractAlpha:
    @pytest.mark.parametrize("fill,expected", [
        ("rgba(0, 0, 255, 0.35)", 0.35),
        ("rgba(255,255,255,1)", 1.0),
        ("rgba(10, 20, 30, 0.5)", 0.5),
    ])
    def test_extracts_alpha(self, conn, fill, expected):
        assert conn.extract_alpha(fill) == expected

    @pytest.mark.parametrize("fill", ["", None, "blue", "#ffffff", "rgb(1,2,3)"])
    def test_missing_alpha_returns_zero(self, conn, fill):
        assert conn.extract_alpha(fill) == 0.0

    def test_higher_alpha_wins_ordering(self, conn):
        """The scraper picks the max-alpha arrow; verify the ordering it relies on."""
        weak = conn.extract_alpha("rgba(0,0,0,0.1)")
        strong = conn.extract_alpha("rgba(0,0,0,0.9)")
        assert strong > weak


class TestGetPointFromPath:
    def test_reads_start_and_end_points(self, conn):
        d = "M 5 6 C 1 2 3 4 7 8"
        assert conn.get_point_from_path(d, 0, 1) == (5.0, 6.0)
        assert conn.get_point_from_path(d, 6, 7) == (7.0, 8.0)

    def test_handles_floats_and_signs(self, conn):
        d = "M 12.5 -3 L 0.25 100"
        assert conn.get_point_from_path(d, 0, 1) == (12.5, 3.0)

    def test_too_few_points_returns_none(self, conn):
        assert conn.get_point_from_path("M 5 6", 6, 7) == (None, None)

    def test_empty_path_returns_none(self, conn):
        assert conn.get_point_from_path("", 0, 1) == (None, None)
        assert conn.get_point_from_path(None, 0, 1) == (None, None)
