import re
from playwright.sync_api import sync_playwright


class PeterSiteConnector:
    """
    Handles live browser automation with Peter's Duck Chess website using Playwright.
    Synchronizes the UI's pixel coordinates with the model's internal (r, c) matrix.

    Coordinate conventions
    -----------------------
    The model frame (see observation_encoder.py) places White's back rank at
    r=7 and Black's at r=0 (White king at (7,4), Black king at (0,4)), with
    c=0 -> file 'a'. The site uses the standard layout (White on rank 1), so
    model rows are vertically mirrored relative to site ranks:
    site_rank = 8 - r. coords_to_algebraic / algebraic_to_coords apply this
    flip (files are preserved); without it every move lands on the wrong side.

    Peter renders 50px squares. With the board NOT flipped (White at the bottom),
    the top-left square a8 sits at (x=0, y=0). 'flipped' tracks the site's
    Flip-Board state: when flipped, Black is at the bottom and the top-left
    square becomes h1, which mirrors BOTH axes of the pixel<->square mapping.
    Algebraic notation itself is orientation-independent (a8 is always a8);
    orientation only affects how pixels map to squares.
    """

    def __init__(self, headless: bool = False):
        self.url = "https://peter.website/duck-chess/analysis"
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=headless)
        self.page = self.browser.new_page()
        self.page.goto(self.url)
        self.page.wait_for_timeout(2000)

        # Orientation of the board as currently drawn on the site.
        # False -> White at bottom (a8 top-left); True -> Black at bottom (h1 top-left).
        self.flipped = False

        # Built once here with the default orientation; rebuilt in init_board()
        # after the real position renders and orientation has been detected.
        self.square_map = self.map_board_squares(self.page)

    # --- ORIENTATION ---------------------------------------------------------

    def detect_orientation(self):
        """
        Determines whether the board is flipped by inspecting where the White
        pieces are rendered. White's pieces occupy the two ranks nearest its
        side, so if most White pieces sit in the bottom half of the board the
        view is unflipped; if they sit in the top half the view is flipped.

        Selector-independent on purpose: we do not rely on the Flip-Board
        control's markup (which we cannot verify), only on piece positions.
        Returns the detected `self.flipped` value.
        """
        pieces = self.page.locator("image").evaluate_all("""
            elems => elems.map(el => ({
                href: el.getAttribute('href'),
                y: parseFloat(el.getAttribute('y'))
            }))
        """)

        bottom, top = 0, 0
        for p in pieces:
            href = p.get('href') or ''
            if 'white' not in href:
                continue
            y = p.get('y')
            if y is None:
                continue
            # Board is 8 * 50 = 400px tall; >= 200 is the bottom half.
            if y >= 200:
                bottom += 1
            else:
                top += 1

        if bottom == 0 and top == 0:
            print("[ORIENT] No White pieces found; assuming default (not flipped).")
            self.flipped = False
        else:
            self.flipped = top > bottom
            print(f"[ORIENT] White pieces top={top} bottom={bottom} -> flipped={self.flipped}")
        return self.flipped

    def pixel_to_file_rank(self, x: float, y: float):
        """Maps a pixel position to (file_idx, rank_idx), each 0-7, honoring flip."""
        col_from_left = int(x / 50)   # 0 = leftmost column on screen
        row_from_top = int(y / 50)    # 0 = top row on screen
        if not self.flipped:
            file_idx = col_from_left          # left -> 'a'
            rank_idx = 7 - row_from_top        # top -> rank 8
        else:
            file_idx = 7 - col_from_left       # left -> 'h'
            rank_idx = row_from_top            # top -> rank 1
        return file_idx, rank_idx

    def pixels_to_algebraic(self, x: float, y: float) -> str:
        """Converts raw browser pixel dimensions to algebraic notation, honoring flip."""
        file_idx, rank_idx = self.pixel_to_file_rank(x, y)
        return f"{chr(ord('a') + file_idx)}{rank_idx + 1}"

    # --- BOARD MAPPING -------------------------------------------------------

    def map_board_squares(self, page):
        """
        Maps algebraic squares (a1..h8) to their Playwright Locator elements,
        using the current orientation so the labels stay correct after a flip.
        """
        squares = page.locator("rect[width='50']")
        page.wait_for_timeout(500)  # Ensure elements are fully bound
        count = squares.count()
        board_map = {}

        for i in range(count):
            square_element = squares.nth(i)
            x = float(square_element.get_attribute('x') or 0)
            y = float(square_element.get_attribute('y') or 0)
            label = self.pixels_to_algebraic(x, y)
            board_map[label] = square_element

        return board_map

    # --- COORDINATE TRANSLATION HELPERS (orientation-independent) ------------

    def coords_to_algebraic(self, r: int, c: int) -> str:
        """Converts model coords (r, c) to site algebraic notation.

        Model frame has White's back rank at r=7, so site_rank = 8 - r
        (files preserved). Without this flip, moves land on the wrong side.
        """
        return f"{chr(ord('a') + c)}{8 - r}"

    def algebraic_to_coords(self, algebraic_str: str):
        """Converts site algebraic notation back to model coords (r, c),
        applying the inverse vertical flip (r = 8 - rank)."""
        c = ord(algebraic_str[0]) - ord('a')
        r = 8 - int(algebraic_str[1])
        return r, c

    def encode_to_action_index(self, start_algebraic: str, end_algebraic: str) -> int:
        """
        Encodes source/destination squares into the 4096 RL action index,
        matching ActionMasker.encode_move: (sr*8+sc)*64 + (er*8+ec).
        The algebraic<->model vertical flip is handled by algebraic_to_coords.
        """
        sr, sc = self.algebraic_to_coords(start_algebraic)
        er, ec = self.algebraic_to_coords(end_algebraic)
        return (sr * 8 + sc) * 64 + (er * 8 + ec)

    def extract_alpha(self, fill_str: str) -> float:
        """Extracts the alpha opacity from rgba fills to find the engine's top choice."""
        if not fill_str:
            return 0.0
        match = re.search(r"rgba\(.*,\s*([\d.]+)\)", fill_str)
        return float(match.group(1)) if match else 0.0

    def get_point_from_path(self, d_attr: str, index_x: int, index_y: int):
        """Parses coordinate points from SVG arrow paths."""
        coords = re.findall(r"[-+]?\d*\.\d+|\d+", d_attr or "")
        coords = [float(c) for c in coords]
        if len(coords) > index_y:
            return coords[index_x], coords[index_y]
        return None, None

    # --- INTERFACE METHODS FOR THE ENV ---------------------------------------

    def send_action_to_site(self, action: int, phase: str):
        """
        Receives a model action, decodes it to internal coords, and replicates
        the click steps on the website. Decoding mirrors ActionMasker.decode_move
        (no vertical flip); the orientation is fully absorbed by square_map.
        """
        start_sq = action // 64
        end_sq = action % 64
        start_coords = (start_sq // 8, start_sq % 8)
        end_coords = (end_sq // 8, end_sq % 8)

        p_src = self.coords_to_algebraic(*start_coords)
        p_dst = self.coords_to_algebraic(*end_coords)

        if phase == 'move_piece':
            if p_src in self.square_map and p_dst in self.square_map:
                self.square_map[p_src].click(force=True)
                self.square_map[p_dst].click(force=True)

        elif phase == 'move_duck':
            if p_dst in self.square_map:
                duck_locator = self.page.locator("image[href*='duck.svg']")
                # If the duck is already deployed on the board, pick it up first
                if duck_locator.count() != 0:
                    duck_locator.click(force=True)
                self.square_map[p_dst].click(force=True)

        self.page.wait_for_timeout(500)

    def receive_actions_from_site(self) -> list:
        """
        Waits for Peter's engine arrows to appear, executes his piece move and
        duck placement on the board, then returns [piece_action, duck_action]
        as 4096-space RL indices.

        Uses wait_for_function instead of a fixed sleep so the scraper only
        proceeds once the DOM actually contains the expected elements.
        """
        p_src, p_dst, p_duck = None, None, None

        # 1. Block until the engine renders a piece-move arrow (rgba-filled path).
        #    A fixed sleep misses slow positions; this fires exactly when ready.
        try:
            self.page.wait_for_function(
                """() => Array.from(document.querySelectorAll('path')).some(p => {
                    const f = p.getAttribute('fill') || '';
                    const m = f.match(/rgba\\(.*?,\\s*([\\d.]+)\\)/);
                    return m && parseFloat(m[1]) > 0;
                })""",
                timeout=30000
            )
        except Exception:
            print("[SCRAPE] Warning: timed out waiting for piece-move arrows.")

        # Scrape the highest-opacity arrow = Peter's best piece move.
        paths = self.page.locator("path")
        best_path = None
        max_alpha = -1
        for i in range(paths.count()):
            p = paths.nth(i)
            alpha = self.extract_alpha(p.get_attribute("fill") or "")
            if alpha > max_alpha:
                max_alpha = alpha
                best_path = p

        if best_path:
            d_attr = best_path.get_attribute("d") or ""
            sx, sy = self.get_point_from_path(d_attr, 0, 1)
            tx, ty = self.get_point_from_path(d_attr, 6, 7)
            if sx is not None and sy is not None:
                p_src = self.pixels_to_algebraic(sx, sy)
                p_dst = self.pixels_to_algebraic(tx, ty)
                print(f"[SCRAPE] Detected Peter Move: {p_src} -> {p_dst}")
                self.square_map[p_src].click(force=True)
                self.square_map[p_dst].click(force=True)

        # 2. Wait for duck-placement circles to appear (blue rgba, r≈20 for best).
        try:
            self.page.wait_for_function(
                """() => document.querySelectorAll('circle[fill*="0.35"]').length > 0""",
                timeout=10000
            )
        except Exception:
            print("[SCRAPE] Warning: timed out waiting for duck placement circles.")

        # Pick up the duck if it is already deployed on the board.
        duck_locator = self.page.locator("image[href*='duck.svg']")
        if duck_locator.count() == 1:
            duck_locator.click(force=True)

        # Largest-radius blue circle = engine's top duck suggestion.
        translucent_circles = self.page.locator('circle[fill*="0.35"]')
        if translucent_circles.count() > 0:
            best_circle, max_radius = None, -1
            for i in range(translucent_circles.count()):
                c = translucent_circles.nth(i)
                r = float(c.get_attribute("r") or 0)
                if r > max_radius:
                    max_radius = r
                    best_circle = c
            if best_circle:
                cx = float(best_circle.get_attribute("cx") or 0)
                cy = float(best_circle.get_attribute("cy") or 0)
                p_duck = self.pixels_to_algebraic(cx, cy)
        else:
            # Fallback: read duck destination from the highest-alpha path arrow.
            paths = self.page.locator("path")
            best_duck_path, max_duck_alpha = None, -1
            for i in range(paths.count()):
                p = paths.nth(i)
                alpha = self.extract_alpha(p.get_attribute("fill") or "")
                if alpha > max_duck_alpha:
                    max_duck_alpha = alpha
                    best_duck_path = p
            if best_duck_path:
                d_attr = best_duck_path.get_attribute("d") or ""
                tx, ty = self.get_point_from_path(d_attr, 6, 7)
                if tx is not None and ty is not None:
                    p_duck = self.pixels_to_algebraic(tx, ty)

        if p_duck:
            print(f"[SCRAPE] Detected Peter Duck Placement: {p_duck}")
            self.square_map[p_duck].click(force=True)

        # Encode back to RL action indices.
        # -1 is used as the failure sentinel (valid indices are always >= 0).
        piece_action_idx = self.encode_to_action_index(p_src, p_dst) if p_src and p_dst else -1
        # Duck uses start_sq 0 (mask convention: encode_move((0,0),(dr,dc))).
        if p_duck:
            dr, dc = self.algebraic_to_coords(p_duck)
            duck_action_idx = dr * 8 + dc
        else:
            duck_action_idx = -1

        return [piece_action_idx, duck_action_idx]

    def init_board(self):
        """Enables analysis, waits for the engine, then locks in orientation."""
        checkbox = self.page.locator("input[type='checkbox']")
        if not checkbox.is_checked():
            checkbox.click()

        self.page.wait_for_function(
            """() => {
                const elements = Array.from(document.querySelectorAll('div'));
                const nodeDiv = elements.find(el => el.innerText.includes('Nodes:'));
                if (!nodeDiv) return false;
                const match = nodeDiv.innerText.match(/Nodes:\\s*(\\d+)/);
                return match && parseInt(match[1]) > 0;
            }""",
            timeout=300000
        )
        print("Engine Active!")

        # Detect the live orientation and rebuild the square map accordingly so
        # all subsequent pixel<->square translations are correct after any flip.
        self.detect_orientation()
        self.square_map = self.map_board_squares(self.page)

    def close(self):
        self.browser.close()
        self.pw.stop()
