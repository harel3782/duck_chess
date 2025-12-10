import pygame
import sys
import random
import os

# --- Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 850
BOARD_SIZE = 800
SQUARE_SIZE = BOARD_SIZE // 8
FPS = 60

# Colors
WHITE_COLOR = (235, 236, 208)
BLACK_SQ_COLOR = (119, 149, 86)
HIGHLIGHT = (186, 202, 68)
VALID_MOVE = (100, 200, 100, 150)
TEXT_COLOR = (20, 20, 20)
BG_COLOR = (240, 240, 240)
BUTTON_COLOR = (70, 130, 180)
BUTTON_HOVER = (100, 149, 237)
MENU_BG = (40, 44, 52)

# Unicode Fallback
UNICODE_PIECES = {
    'w': {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙'},
    'b': {'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟'}
}

KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN = 'K', 'Q', 'R', 'B', 'N', 'P'


class Piece:
    def __init__(self, color, type):
        self.color = color
        self.type = type
        self.has_moved = False


class DuckChess:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Duck Chess: Resized Duck")
        self.clock = pygame.time.Clock()

        self.font_large = pygame.font.SysFont("Segoe UI Symbol", int(SQUARE_SIZE * 0.8), bold=True)
        self.font_ui = pygame.font.SysFont("Arial", 20)
        self.font_menu = pygame.font.SysFont("Arial", 40, bold=True)

        self.restart_btn_rect = pygame.Rect(650, 810, 130, 30)
        self.menu_btn_rect = pygame.Rect(500, 810, 130, 30)

        # Game Config
        self.game_mode = None  # 'white_ai', 'black_ai', 'pvp'
        self.player_side = 'w'  # Perspective
        self.state = 'menu'  # 'menu' or 'game'

        # --- LOAD ASSETS ---
        self.images = {}
        self.load_assets()

        # Initialize empty state
        self.reset_game_state()

    def load_assets(self):
        """Loads the spritesheet for pieces and the individual duck image."""
        # 1. Load Pieces Spritesheet
        filename = "assets/pieces.png"
        if os.path.exists(filename):
            try:
                sheet = pygame.image.load(filename).convert_alpha()
                sheet_width, sheet_height = sheet.get_size()
                cols, rows = 6, 2
                sprite_w = sheet_width // cols
                sprite_h = sheet_height // rows
                piece_order = [QUEEN, KING, ROOK, KNIGHT, BISHOP, PAWN]
                row_map = {0: 'b', 1: 'w'}  # Top row black, bottom white

                for row in range(rows):
                    color = row_map[row]
                    for col in range(cols):
                        rect = pygame.Rect(col * sprite_w, row * sprite_h, sprite_w, sprite_h)
                        image = sheet.subsurface(rect)
                        image = pygame.transform.smoothscale(image, (SQUARE_SIZE, SQUARE_SIZE))
                        self.images[f"{color}{piece_order[col]}"] = image
            except pygame.error as e:
                print(f"Error loading pieces.png: {e}")
        else:
            print(f"Sprite sheet not found at {filename}. Using text fallback for pieces.")

        # 2. Load Duck Image
        duck_file = "assets/duck.png"
        if os.path.exists(duck_file):
            try:
                img = pygame.image.load(duck_file).convert_alpha()
                # Scale duck to 80% of square size for a better fit
                duck_size = int(SQUARE_SIZE * 0.8)
                img = pygame.transform.smoothscale(img, (duck_size, duck_size))
                self.images['duck'] = img
            except pygame.error as e:
                print(f"Error loading duck.png: {e}")
        else:
            print(f"Duck image not found at {duck_file}. Using procedural fallback.")

    def reset_game_state(self):
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.init_board()
        self.duck_pos = (-1, -1)
        self.turn = 'w'
        self.phase = 'move_piece'
        self.selected_square = None
        self.valid_moves = []
        self.game_over = False
        self.winner = None

    def init_board(self):
        setup = [
            (ROOK, 0, 0), (KNIGHT, 0, 1), (BISHOP, 0, 2), (QUEEN, 0, 3), (KING, 0, 4), (BISHOP, 0, 5), (KNIGHT, 0, 6),
            (ROOK, 0, 7),
            (ROOK, 7, 0), (KNIGHT, 7, 1), (BISHOP, 7, 2), (QUEEN, 7, 3), (KING, 7, 4), (BISHOP, 7, 5), (KNIGHT, 7, 6),
            (ROOK, 7, 7)
        ]
        for p_type, r, c in setup:
            color = 'b' if r == 0 else 'w'
            self.board[r][c] = Piece(color, p_type)
        for c in range(8):
            self.board[1][c] = Piece('b', PAWN)
            self.board[6][c] = Piece('w', PAWN)

    # --- Coordinate Transformation ---
    def get_screen_pos(self, r, c):
        """Converts board coords (r,c) to screen coords (x,y) based on player perspective."""
        if self.player_side == 'b':
            # Flip board: Row 0 is bottom, Col 0 is right
            draw_r = 7 - r
            draw_c = 7 - c
        else:
            # Standard White perspective
            draw_r = r
            draw_c = c
        return draw_c * SQUARE_SIZE, draw_r * SQUARE_SIZE

    def get_board_pos(self, x, y):
        """Converts screen coords (x,y) to board coords (r,c) based on player perspective."""
        col = x // SQUARE_SIZE
        row = y // SQUARE_SIZE
        if self.player_side == 'b':
            return 7 - row, 7 - col
        return row, col

    # --- Game Logic ---
    def get_piece_legal_moves(self, r, c):
        piece = self.board[r][c]
        if not piece: return []
        moves = []

        # Castling
        if piece.type == KING and not piece.has_moved:
            if self.can_castle(r, c, is_kingside=True): moves.append((r, 6))
            if self.can_castle(r, c, is_kingside=False): moves.append((r, 2))

        directions = []
        if piece.type in [KING, QUEEN]:
            directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif piece.type == ROOK:
            directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        elif piece.type == BISHOP:
            directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif piece.type == KNIGHT:
            for dr, dc in [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and (nr, nc) != self.duck_pos:
                    target = self.board[nr][nc]
                    if target is None or target.color != piece.color: moves.append((nr, nc))
            return moves
        elif piece.type == PAWN:
            d = -1 if piece.color == 'w' else 1
            if 0 <= r + d < 8 and not self.board[r + d][c] and (r + d, c) != self.duck_pos:
                moves.append((r + d, c))
                start_row = 6 if piece.color == 'w' else 1
                if r == start_row and not self.board[r + d * 2][c] and (r + d * 2, c) != self.duck_pos:
                    moves.append((r + d * 2, c))
            for dc in [-1, 1]:
                nr, nc = r + d, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    target = self.board[nr][nc]
                    if target and target.color != piece.color and (nr, nc) != self.duck_pos:
                        moves.append((nr, nc))
            return moves

        # Sliding Pieces
        max_dist = 1 if piece.type == KING else 8
        for dr, dc in directions:
            for dist in range(1, max_dist + 1):
                nr, nc = r + dr * dist, c + dc * dist
                if not (0 <= nr < 8 and 0 <= nc < 8): break
                if (nr, nc) == self.duck_pos: break
                target = self.board[nr][nc]
                if target is None:
                    moves.append((nr, nc))
                else:
                    if target.color != piece.color: moves.append((nr, nc))
                    break
        return moves

    def can_castle(self, r, c, is_kingside):
        rook_col = 7 if is_kingside else 0
        rook = self.board[r][rook_col]
        if not rook or rook.type != ROOK or rook.has_moved: return False
        path_cols = [5, 6] if is_kingside else [1, 2, 3]
        for col in path_cols:
            if self.board[r][col] is not None or (r, col) == self.duck_pos: return False
        return True

    def execute_move(self, start, end):
        sr, sc = start
        er, ec = end
        piece = self.board[sr][sc]
        target = self.board[er][ec]

        if target and target.type == KING:
            self.game_over = True
            self.winner = self.turn

        if piece.type == KING and abs(sc - ec) == 2:
            is_kingside = (ec > sc)
            rook_col, new_rook_col = (7, 5) if is_kingside else (0, 3)
            rook = self.board[sr][rook_col]
            self.board[sr][new_rook_col] = rook
            self.board[sr][rook_col] = None
            rook.has_moved = True

        self.board[er][ec] = piece
        self.board[sr][sc] = None
        piece.has_moved = True

        if not self.game_over:
            self.phase = 'move_duck'

    def place_duck(self, pos):
        self.duck_pos = pos
        self.phase = 'move_piece'
        self.turn = 'b' if self.turn == 'w' else 'w'

    # --- Interaction ---
    def handle_click(self, pos):
        # Always check bottom UI buttons
        if self.restart_btn_rect.collidepoint(pos):
            self.reset_game_state()
            return
        if self.menu_btn_rect.collidepoint(pos):
            self.state = 'menu'
            return

        if self.game_over: return

        # If AI turn (and we are not in PVP), ignore click
        is_ai_turn = (self.game_mode == 'white_ai' and self.turn == 'b') or \
                     (self.game_mode == 'black_ai' and self.turn == 'w')
        if is_ai_turn: return

        # Transform click to board coordinates
        row, col = self.get_board_pos(pos[0], pos[1])
        if row < 0 or row >= 8 or col < 0 or col >= 8: return

        if self.phase == 'move_piece':
            clicked = self.board[row][col]
            if clicked and clicked.color == self.turn:
                self.selected_square = (row, col)
                self.valid_moves = self.get_piece_legal_moves(row, col)
            elif self.selected_square and (row, col) in self.valid_moves:
                self.execute_move(self.selected_square, (row, col))
                self.selected_square = None
                self.valid_moves = []
        elif self.phase == 'move_duck':
            if self.board[row][col] is None:
                self.place_duck((row, col))

    def ai_turn(self):
        if self.game_over: return

        # Check if it's actually AI's turn based on mode
        is_ai_turn = (self.game_mode == 'white_ai' and self.turn == 'b') or \
                     (self.game_mode == 'black_ai' and self.turn == 'w')
        if not is_ai_turn: return

        if self.phase == 'move_piece':
            moves = []
            for r in range(8):
                for c in range(8):
                    p = self.board[r][c]
                    if p and p.color == self.turn:
                        for m in self.get_piece_legal_moves(r, c):
                            moves.append(((r, c), m))

            if not moves:
                self.turn = 'w' if self.turn == 'b' else 'b'  # Pass turn if stuck
                return

            move = random.choice(moves)
            pygame.time.wait(300)
            self.execute_move(move[0], move[1])

        if self.phase == 'move_duck' and not self.game_over:
            empties = [(r, c) for r in range(8) for c in range(8) if self.board[r][c] is None]
            if empties:
                pygame.time.wait(200)
                self.place_duck(random.choice(empties))

    # --- Rendering ---
    def draw_duck(self, r, c):
        """Draws the duck image if available, otherwise a static procedural duck."""
        x, y = self.get_screen_pos(r, c)

        if 'duck' in self.images:
            # Use the loaded image. Center it in the square.
            duck_img = self.images['duck']
            img_rect = duck_img.get_rect(center=(x + SQUARE_SIZE // 2, y + SQUARE_SIZE // 2))
            self.screen.blit(duck_img, img_rect)
        else:
            # Static Procedural Duck Fallback (No animation)
            pygame.draw.ellipse(self.screen, (135, 206, 235), (x + 5, y + 55, 90, 30))  # Water
            pygame.draw.ellipse(self.screen, (255, 220, 0), (x + 15, y + 45, 70, 40))
            pygame.draw.circle(self.screen, (255, 220, 0), (int(x + 70), int(y + 40)), 20)
            pygame.draw.polygon(self.screen, (255, 165, 0), [(x + 85, y + 35), (x + 100, y + 40), (x + 85, y + 45)])
            pygame.draw.circle(self.screen, (255, 255, 255), (int(x + 75), int(y + 35)), 6)
            pygame.draw.circle(self.screen, (0, 0, 0), (int(x + 77), int(y + 35)), 3)
            pygame.draw.ellipse(self.screen, (230, 200, 0), (x + 30, y + 55, 40, 20))

    def draw_game(self):
        self.screen.fill(BG_COLOR)

        # Board
        for r in range(8):
            for c in range(8):
                x, y = self.get_screen_pos(r, c)
                color = WHITE_COLOR if (r + c) % 2 == 0 else BLACK_SQ_COLOR
                pygame.draw.rect(self.screen, color, (x, y, SQUARE_SIZE, SQUARE_SIZE))

                # Selection
                if self.selected_square == (r, c):
                    pygame.draw.rect(self.screen, HIGHLIGHT, (x, y, SQUARE_SIZE, SQUARE_SIZE))

                # Valid Moves
                if (r, c) in self.valid_moves:
                    s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE))
                    s.set_alpha(100)
                    s.fill((0, 255, 0))
                    self.screen.blit(s, (x, y))

                # Duck
                if self.duck_pos == (r, c):
                    self.draw_duck(r, c)

                # Pieces
                piece = self.board[r][c]
                if piece:
                    key = f"{piece.color}{piece.type}"
                    if key in self.images:
                        self.screen.blit(self.images[key], (x, y))
                    else:
                        text = UNICODE_PIECES[piece.color][piece.type]
                        p_color = (0, 0, 0) if piece.color == 'b' else (255, 255, 255)
                        txt_surf = self.font_large.render(text, True, p_color)
                        rect = txt_surf.get_rect(center=(x + SQUARE_SIZE // 2, y + SQUARE_SIZE // 2))
                        if piece.color == 'w':
                            outline = self.font_large.render(text, True, (0, 0, 0))
                            out_rect = outline.get_rect(center=(x + SQUARE_SIZE // 2 + 2, y + SQUARE_SIZE // 2 + 2))
                            self.screen.blit(outline, out_rect)
                        self.screen.blit(txt_surf, rect)

        # UI Bar
        pygame.draw.rect(self.screen, (220, 220, 220), (0, 800, SCREEN_WIDTH, 50))
        if self.game_over:
            status = f"GAME OVER! {'White' if self.winner == 'w' else 'Black'} Wins!"
        else:
            status = f"{'White' if self.turn == 'w' else 'Black'} | {'Move Piece' if self.phase == 'move_piece' else 'Place Duck'}"

        txt = self.font_ui.render(status, True, TEXT_COLOR)
        self.screen.blit(txt, (20, 812))

        # Buttons
        mouse_pos = pygame.mouse.get_pos()

        # Restart Button
        btn_col = BUTTON_HOVER if self.restart_btn_rect.collidepoint(mouse_pos) else BUTTON_COLOR
        pygame.draw.rect(self.screen, btn_col, self.restart_btn_rect, border_radius=5)
        btn_txt = self.font_ui.render("Restart", True, (255, 255, 255))
        self.screen.blit(btn_txt, btn_txt.get_rect(center=self.restart_btn_rect.center))

        # Menu Button
        btn_col = BUTTON_HOVER if self.menu_btn_rect.collidepoint(mouse_pos) else BUTTON_COLOR
        pygame.draw.rect(self.screen, btn_col, self.menu_btn_rect, border_radius=5)
        btn_txt = self.font_ui.render("Menu", True, (255, 255, 255))
        self.screen.blit(btn_txt, btn_txt.get_rect(center=self.menu_btn_rect.center))

    def draw_menu(self):
        self.screen.fill(MENU_BG)

        title = self.font_menu.render("DUCK CHESS", True, (255, 215, 0))
        self.screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 200)))

        # Menu Buttons
        opts = [
            ("Play as White (vs AI)", 'white_ai'),
            ("Play as Black (vs AI)", 'black_ai'),
            ("2 Player Mode", 'pvp')
        ]

        start_y = 350
        mouse_pos = pygame.mouse.get_pos()

        for i, (text, mode) in enumerate(opts):
            rect = pygame.Rect(SCREEN_WIDTH // 2 - 150, start_y + i * 80, 300, 60)
            col = BUTTON_HOVER if rect.collidepoint(mouse_pos) else BUTTON_COLOR
            pygame.draw.rect(self.screen, col, rect, border_radius=10)

            txt_surf = self.font_ui.render(text, True, (255, 255, 255))
            self.screen.blit(txt_surf, txt_surf.get_rect(center=rect.center))

            # Check click inside draw loop (simple method for menu)
            if pygame.mouse.get_pressed()[0] and rect.collidepoint(mouse_pos):
                self.game_mode = mode
                self.player_side = 'b' if mode == 'black_ai' else 'w'
                self.reset_game_state()
                self.state = 'game'
                pygame.time.wait(200)  # Debounce

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and self.state == 'game':
                    self.handle_click(event.pos)

            if self.state == 'menu':
                self.draw_menu()
            else:
                self.ai_turn()
                self.draw_game()

            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    DuckChess().run()