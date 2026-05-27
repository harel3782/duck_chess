import re
from playwright.sync_api import sync_playwright


class PeterSiteConnector:
    """
    Handles live browser automation with Peter's Duck Chess website using Playwright.
    Synchronizes the UI's pixel coordinates with the model's internal (r, c) matrix.

    Coordinate conventions
    -----------------------
    Internal model coords are (r, c) with r=0 -> rank 1, c=0 -> file 'a', so
    (0,0)=a1 and (7,0)=a8 (consistent with ActionMasker.encode_move and
    BitboardManager.coords_to_square = r*8 + c).

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

        print(f"[UI] Board Mapping Completed: Mapped {len(board_map)} square locators "
              f"(flipped={self.flipped}).")
        return board_map

    # --- COORDINATE TRANSLATION HELPERS (orientation-independent) ------------

    def coords_to_algebraic(self, r: int, c: int) -> str:
        """Converts model matrix coordinates (r, c) to standard chess notation."""
        return f"{chr(ord('a') + c)}{r + 1}"

    def algebraic_to_coords(self, algebraic_str: str):
        """Converts standard chess notation back to model matrix coordinates (r, c)."""
        c = ord(algebraic_str[0]) - ord('a')
        r = int(algebraic_str[1]) - 1
        return r, c

    def encode_to_action_index(self, start_algebraic: str, end_algebraic: str) -> int:
        """
        Encodes source/destination squares into the 4096 RL action index.
        Mirrors ActionMasker.encode_move exactly: (sr*8+sc)*64 + (er*8+ec),
        with NO vertical flip (the previous 7-r flip mis-mirrored every move).
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
            print(f"[ACTION] Physically Moving Piece: {p_src} -> {p_dst}")
            if p_src in self.square_map and p_dst in self.square_map:
                self.square_map[p_src].click(force=True)
                self.square_map[p_dst].click(force=True)

        elif phase == 'move_duck':
            print(f"[ACTION] Physically Placing Duck: {p_dst}")
            if p_dst in self.square_map:
                duck_locator = self.page.locator("image[href*='duck.svg']")
                # If the duck is already deployed on the board, pick it up first
                if duck_locator.count() != 0:
                    duck_locator.click(force=True)
                self.square_map[p_dst].click(force=True)

        self.page.wait_for_timeout(500)

    def receive_actions_from_site(self) -> list:
        """
        Scrapes Peter's engine evaluation arrows/circles, executes them on the
        board, and returns them as [piece_action, duck_action] in the model's
        4096 action index space.
        """
        self.page.wait_for_timeout(3000)  # Wait for engine calculation to settle

        p_src, p_dst, p_duck = None, None, None

        # 1. Scrape the best piece-move arrow (highest-opacity path)
        paths = self.page.locator("path")
        count = paths.count()
        best_path = None
        max_alpha = -1

        for i in range(count):
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

        self.page.wait_for_timeout(500)

        # 2. Scrape the best duck placement (arrow target or translucent circle)
        duck_locator = self.page.locator("image[href*='duck.svg']")
        if duck_locator.count() == 1:
            duck_locator.click(force=True)

        translucent_circles = self.page.locator('circle[fill*="0.35"]')

        if translucent_circles.count() == 0:
            paths = self.page.locator("path")
            best_duck_path = None
            max_duck_alpha = -1

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
        else:
            best_circle = None
            max_radius = -1
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

        if p_duck:
            print(f"[SCRAPE] Detected Peter Duck Placement: {p_duck}")
            self.square_map[p_duck].click(force=True)

        # Encode strings back into the standard RL environment indices.
        piece_action_idx = self.encode_to_action_index(p_src, p_dst) if p_src and p_dst else 0
        # Duck moves only use the destination; 'a1' is a harmless dummy start
        # (encodes to start index 0, matching the duck action mask convention).
        duck_action_idx = self.encode_to_action_index("a1", p_duck) if p_duck else 0

        return [piece_action_idx, duck_action_idx]

    def init_board(self):
        """Enables analysis, waits for the engine, then locks in orientation."""
        checkbox = self.page.locator("input[type='checkbox']")
        if not checkbox.is_checked():
            checkbox.click()

        print("Waiting for engine to initialize (Nodes > 0)...")
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
