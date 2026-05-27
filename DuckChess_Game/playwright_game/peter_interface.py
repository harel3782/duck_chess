from playwright.sync_api import sync_playwright
import re

from DuckChess_Game.Logic.bitboard_manager import BitboardManager

class PeterInterface:
    """
    Handles all browser interactions with peter.website.
    Translates internal board coordinates to algebraic moves and DOM interactions.
    """

    PIECE_NAME_TO_ID = {
        'PAWN': 'P',
        'ROOK': 'R',
        'KNIGHT': 'N',
        'BISHOP': 'B',
        'QUEEN': 'Q',
        'KING': 'K'
    }

    def __init__(self, headless=False):
        self.url = "https://peter.website/duck-chess/analysis"
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=headless)
        self.page = self.browser.new_page()
        self.page.goto(self.url)
        self.page.wait_for_timeout(2000)
        self.square_map = self.map_board_squares(self.page)
    
    def get_page(self):
        return self.page

    def reset(self):
        self.page.goto(self.url)
        self.page.wait_for_timeout(2000)

    def map_board_squares(self, page):
        """Maps algebraic squares (a1 to h8) to their Playwright Locator elements."""
        squares = page.locator("rect[width='50']")
        count = squares.count()
        board_map = {}

        for i in range(count):
            square_element = squares.nth(i)
            # Fetch x and y just to calculate the algebraic label
            x = float(square_element.get_attribute('x'))
            y = float(square_element.get_attribute('y'))

            # File (Column): 0->a, 50->b, 100->c ...
            file_letter = chr(ord('a') + int(x / 50))
            # Model View Conversion: 
            # y=0 (top, black) -> should be row 7 for model
            # y=350 (bottom, white) -> should be row 0 for model
            model_r = 7 - int(y / 50)

            rank_number = str(model_r + 1)
            
            label = f"{file_letter}{rank_number}"

            # Save the actual Playwright element locator
            board_map[label] = square_element
            
        print(f"[UI] Board Mapping Completed: Mapped {len(board_map)} element locators.")
        return board_map

    def coords_to_algebraic(self, r, c):
        """Converts internal engine row/col to algebraic based entirely on Model's view (0,0 -> a1)."""
        file_letter = chr(ord('a') + c)
        rank_number = r + 1
        return f"{file_letter}{rank_number}"

    def algebraic_to_coords(self, alg):
        """Converts algebraic notation back to internal engine row/col (a1 -> 0,0)."""
        if not alg:  # Safety check for None or empty string
            return -1, -1
        files = "abcdefgh"
        c = files.index(alg[0])
        r = int(alg[1]) - 1
        return r, c

    def extract_alpha(self, fill_str):
        if not fill_str: return 0.0
        match = re.search(r"rgba\(.*,\s*([\d.]+)\)", fill_str)
        return float(match.group(1)) if match else 0.0

    def get_point_from_path(self, d_attr, index_x, index_y):
        coords = re.findall(r"[-+]?\d*\.\d+|\d+", d_attr)
        coords = [float(c) for c in coords]
        if len(coords) > index_y:
            return coords[index_x], coords[index_y]
        return None, None

    def map_to_bitboard(self, page):
        """Scrapes the SVG for pieces and populated BitboardManager."""
        manager = BitboardManager()
        manager.duck_pos = None

        piece_elements = page.locator("image").evaluate_all("""
            elems => elems.map(el => ({
                href: el.getAttribute('href'),
                x: parseFloat(el.getAttribute('x')),
                y: parseFloat(el.getAttribute('y'))
            }))
        """)

        for p in piece_elements:
            href = p.get('href')
            if not href or '_' not in href: continue
            if 'white' not in href and 'black' not in href: continue
            
            filename = href.split('/')[-1]
            color = 'w' if 'white' in filename else 'b'
            raw_type = filename.split('_')[1].replace('.svg', '').upper()
            piece_type = self.PIECE_NAME_TO_ID.get(raw_type, raw_type)     

            c = int(p['x'] / 50)
            r = 7 - int(p['y'] / 50)
            print(f"Found piece: {color} {piece_type} at (r={r}, c={c})")
            manager.add_piece(color, piece_type, r, c)

        circles = page.locator("circle").evaluate_all("""
            elems => elems.map(el => ({
                r: parseFloat(el.getAttribute('r')),
                cx: parseFloat(el.getAttribute('cx')),
                cy: parseFloat(el.getAttribute('cy')),
                fill: el.getAttribute('fill')
            }))
        """)
        
        duck_circles = [c for c in circles if "0.35" in str(c['fill'])]
        if duck_circles:
            duck_circles.sort(key=lambda x: x['r'], reverse=True)
            duck = duck_circles[0]
            duck_c = int((duck['cx'] - 25) / 50)
            duck_r = 7 - int((duck['cy'] - 25) / 50)
            manager.move_duck(duck_r, duck_c)
            manager.duck_pos = (duck_r, duck_c)

        return manager

    def model_move(self, action, board_map, engine):
        """Translates and performs the model's action directly on the website UI."""
        start, end = engine._decode_move(action)
        p_src = self.coords_to_algebraic(start[0], start[1])
        p_dst = self.coords_to_algebraic(end[0], end[1])

        if engine.phase == 'move_piece':
            print(f"[ACTION] Model Piece Move: {p_src} -> {p_dst}")
            if p_src in board_map and p_dst in board_map:
                board_map[p_src].click(force=True)
                board_map[p_dst].click(force=True)
        elif engine.phase == 'move_duck':
            print(f"[ACTION] Model Duck Placement: {p_dst}")
            if p_dst in board_map:
                duck_locator = self.get_page().locator("image[href*='duck.svg']")
                if duck_locator.count() != 0:
                    duck_locator.click(force=True)
                board_map[p_dst].click(force=True)
        self.page.wait_for_timeout(500)

    def execute_peter_response(self, map_board):
        """Scrapes and executes Peter's engine UI suggestions."""
        self.page.wait_for_timeout(3000)

        def pixels_to_algebraic(x, y):
            file_letter = chr(ord('a') + int(x / 50))
            rank_number = 8 - int(y / 50)
            return f"{file_letter}{rank_number}"

        p_src, p_dst, p_duck = None, None, None
        last_p_duck = None
        
        # 1. Scrape Piece Move
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
            d_attr = best_path.get_attribute("d")
            sx, sy = self.get_point_from_path(d_attr, 0, 1)
            tx, ty = self.get_point_from_path(d_attr, 6, 7)

            if sx is not None and sy is not None:
                p_src = pixels_to_algebraic(sx, sy)
                p_dst = pixels_to_algebraic(tx, ty)                
                print(f"[ACTION] Peter Piece Move: {p_src} -> {p_dst}")
                map_board[p_src].click(force=True)
                map_board[p_dst].click(force=True)
            
        self.page.wait_for_timeout(500)
        
        # 2. Scrape Duck Move
        duck_locator = self.page.locator("image[href*='duck.svg']")
        if duck_locator.count() == 1:
            box = duck_locator.bounding_box()
            if box:
                last_p_duck = pixels_to_algebraic(box['x'], box['y'])
            duck_locator.click(force=True)

        translucentCircles = self.page.locator('circle[fill*="0.35"]')
        if translucentCircles.count() == 0:
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
                d_attr = best_path.get_attribute("d")
                tx, ty = self.get_point_from_path(d_attr, 6, 7)
                if tx is not None and ty is not None:
                    p_duck = pixels_to_algebraic(tx, ty)
                    print(f"[ACTION] Peter Duck Placement: {p_duck}")        
                    map_board[p_duck].click(force=True)
        else:        
            best_circle = None
            max_radius = -1  # Fixed Syntax Error
        
            for i in range(translucentCircles.count()):
                c = translucentCircles.nth(i)
                r = float(c.get_attribute("r") or 0)
                if r > max_radius:
                    max_radius = r
                    best_circle = c
            if best_circle:
                cx = float(best_circle.get_attribute("cx"))
                cy = float(best_circle.get_attribute("cy"))
                p_duck = pixels_to_algebraic(cx, cy)
                print(f"[ACTION] Peter Duck Placement: {p_duck}")        
                map_board[p_duck].click(force=True)

        return p_src, p_dst, last_p_duck, p_duck
    
    def wait_for_timeout(self, page):
        page.wait_for_timeout(3000)