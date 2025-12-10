import pygame
import sys
import random

# --- Constants & Configuration ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 850  # Extra space for status text
BOARD_SIZE = 800
SQUARE_SIZE = BOARD_SIZE // 8
FPS = 60

# Colors
WHITE = (235, 236, 208)
BLACK_SQ = (119, 149, 86)  # Greenish pleasant color
HIGHLIGHT = (186, 202, 68)  # Selected piece square
VALID_MOVE = (100, 200, 100, 150)  # Transparent green for moves
DUCK_COLOR = (255, 215, 0)  # Gold/Yellow
TEXT_COLOR = (20, 20, 20)
BG_COLOR = (240, 240, 240)

# Unicode Chess Pieces
UNICODE_PIECES = {
    'w': {'K': '♔', 'Q': '♕', 'R': '♖', 'B': '♗', 'N': '♘', 'P': '♙'},
    'b': {'K': '♚', 'Q': '♛', 'R': '♜', 'B': '♝', 'N': '♞', 'P': '♟'}
}

# Piece Types
KING, QUEEN, ROOK, BISHOP, KNIGHT, PAWN = 'K', 'Q', 'R', 'B', 'N', 'P'


class Piece:
    def __init__(self, color, type):
        self.color = color  # 'w' or 'b'
        self.type = type  # 'K', 'Q', 'R', 'B', 'N', 'P'
        self.has_moved = False


class DuckChess:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Duck Chess - Python Senior Dev Edition")
        self.clock = pygame.time.Clock()
        self.font_large = pygame.font.SysFont("Segoe UI Symbol", int(SQUARE_SIZE * 0.8), bold=True)
        self.font_ui = pygame.font.SysFont("Arial", 24)

        # Game State
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.duck_pos = None  # (row, col)
        self.turn = 'w'  # 'w' or 'b'
        self.phase = 'move_piece'  # 'move_piece' or 'move_duck'
        self.selected_square = None
        self.valid_moves = []
        self.game_over = False
        self.winner = None

        self.init_board()
        # Place duck initially off-board or at a specific spot. 
        # Standard rules often have players place it first, but for simplicity, 
        # we start without it on board or imply it's "in hand". 
        # Here: The duck starts off-board, first player places it after move.
        self.duck_pos = (-1, -1)

    def draw_rubber_duck(self, r, c):
        """Draws a cute procedural rubber duck at row r, col c."""
        x = c * SQUARE_SIZE
        y = r * SQUARE_SIZE
        offset_x = x + SQUARE_SIZE // 2
        offset_y = y + SQUARE_SIZE // 2

        # 1. Body (Yellow Ellipse)
        body_rect = pygame.Rect(x + 15, y + 45, 70, 40)
        pygame.draw.ellipse(self.screen, (255, 220, 0), body_rect)

        # 2. Head (Yellow Circle)
        pygame.draw.circle(self.screen, (255, 220, 0), (x + 70, y + 40), 20)

        # 3. Beak (Orange Triangle/Polygon)
        beak_points = [(x + 85, y + 35), (x + 100, y + 40), (x + 85, y + 45)]
        pygame.draw.polygon(self.screen, (255, 165, 0), beak_points)

        # 4. Eye (White outer, Black pupil)
        pygame.draw.circle(self.screen, (255, 255, 255), (x + 75, y + 35), 6)
        pygame.draw.circle(self.screen, (0, 0, 0), (x + 77, y + 35), 3)

        # 5. Wing (Darker Yellow Arc/Ellipse)
        wing_rect = pygame.Rect(x + 30, y + 55, 40, 20)
        pygame.draw.ellipse(self.screen, (230, 200, 0), wing_rect)

    def init_board(self):
        """Sets up the standard chess board."""
        setup = [
            (ROOK, 0, 0), (KNIGHT, 0, 1), (BISHOP, 0, 2), (QUEEN, 0, 3), (KING, 0, 4), (BISHOP, 0, 5), (KNIGHT, 0, 6),
            (ROOK, 0, 7),
            (ROOK, 7, 0), (KNIGHT, 7, 1), (BISHOP, 7, 2), (QUEEN, 7, 3), (KING, 7, 4), (BISHOP, 7, 5), (KNIGHT, 7, 6),
            (ROOK, 7, 7)
        ]

        # Place Pieces
        for p_type, r, c in setup:
            color = 'b' if r == 0 else 'w'
            self.board[r][c] = Piece(color, p_type)

        # Pawns
        for c in range(8):
            self.board[1][c] = Piece('b', PAWN)
            self.board[6][c] = Piece('w', PAWN)

    def get_piece_legal_moves(self, r, c):
        """
        Returns a list of (r, c) tuples representing valid moves.
        Includes Castling logic (King side & Queen side).
        """
        piece = self.board[r][c]
        if not piece: return []

        moves = []

        # --- CASTLING LOGIC (Specific to King) ---
        if piece.type == KING and not piece.has_moved:
            # Kingside Castling (Target: G-file, i.e., col 6)
            # Conditions: Rook exists @ col 7, hasn't moved, path (5,6) is empty & no Duck
            if self.can_castle(r, c, is_kingside=True):
                moves.append((r, 6))

            # Queenside Castling (Target: C-file, i.e., col 2)
            # Conditions: Rook exists @ col 0, hasn't moved, path (1,2,3) is empty & no Duck
            if self.can_castle(r, c, is_kingside=False):
                moves.append((r, 2))

        # --- STANDARD MOVES (Same as before) ---
        directions = []
        if piece.type == KING:
            directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif piece.type == QUEEN:
            directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif piece.type == ROOK:
            directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        elif piece.type == BISHOP:
            directions = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        elif piece.type == KNIGHT:
            knight_moves = [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]
            for dr, dc in knight_moves:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    if (nr, nc) == self.duck_pos: continue
                    target = self.board[nr][nc]
                    if target is None or target.color != piece.color:
                        moves.append((nr, nc))
            return moves
        elif piece.type == PAWN:
            direction = -1 if piece.color == 'w' else 1
            nr, nc = r + direction, c
            if 0 <= nr < 8 and self.board[nr][nc] is None and (nr, nc) != self.duck_pos:
                moves.append((nr, nc))
                is_start = (r == 6 and piece.color == 'w') or (r == 1 and piece.color == 'b')
                nr2 = r + (direction * 2)
                if is_start and self.board[nr2][nc] is None and (nr2, nc) != self.duck_pos:
                    moves.append((nr2, nc))
            for dc in [-1, 1]:
                nr, nc = r + direction, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    target = self.board[nr][nc]
                    if target and target.color != piece.color and (nr, nc) != self.duck_pos:
                        moves.append((nr, nc))
            return moves

        # Sliding Logic (R, B, Q, K)
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
                    if target.color != piece.color:
                        moves.append((nr, nc))
                    break
        return moves

    def can_castle(self, r, c, is_kingside):
        """Helper to check castling conditions including Duck block."""
        rook_col = 7 if is_kingside else 0
        rook = self.board[r][rook_col]

        # 1. Check Rook
        if not rook or rook.type != ROOK or rook.has_moved:
            return False

        # 2. Check Path Clearance (Pieces & Duck)
        # Kingside path: cols 5, 6. Queenside path: cols 1, 2, 3
        path_cols = [5, 6] if is_kingside else [1, 2, 3]

        for col in path_cols:
            # Check for Piece
            if self.board[r][col] is not None:
                return False
            # Check for Duck
            if (r, col) == self.duck_pos:
                return False

        return True
    def handle_click(self, pos):
        """Handles mouse input for human player."""
        if self.game_over or (self.turn == 'b'): return

        col = pos[0] // SQUARE_SIZE
        row = pos[1] // SQUARE_SIZE

        # Validate click is within board
        if row >= 8 or col >= 8: return

        if self.phase == 'move_piece':
            clicked_piece = self.board[row][col]

            # Select a piece
            if clicked_piece and clicked_piece.color == self.turn:
                self.selected_square = (row, col)
                self.valid_moves = self.get_piece_legal_moves(row, col)

            # Move selected piece
            elif self.selected_square:
                if (row, col) in self.valid_moves:
                    self.execute_move(self.selected_square, (row, col))
                    self.selected_square = None
                    self.valid_moves = []

        elif self.phase == 'move_duck':
            # Place duck on empty square
            if self.board[row][col] is None:
                # Duck cannot remain on same square (implied by "move" the duck, 
                # but technically user could click the old duck pos if empty. 
                # We simply allow any empty square.)
                self.place_duck((row, col))

    def execute_move(self, start, end):
        """Moves piece, checks win condition, handles Castling."""
        sr, sc = start
        er, ec = end

        piece = self.board[sr][sc]
        target = self.board[er][ec]

        # Check Win Condition (King Capture)
        if target and target.type == KING:
            self.game_over = True
            self.winner = self.turn

        # --- CASTLING EXECUTION ---
        # If King moves 2 squares horizontally, it's a castle
        if piece.type == KING and abs(sc - ec) == 2:
            is_kingside = (ec > sc)  # Moving right
            rook_col = 7 if is_kingside else 0
            new_rook_col = 5 if is_kingside else 3

            # Move the Rook
            rook = self.board[sr][rook_col]
            self.board[sr][new_rook_col] = rook
            self.board[sr][rook_col] = None
            rook.has_moved = True

        # Standard Move
        self.board[er][ec] = piece
        self.board[sr][sc] = None
        piece.has_moved = True

        # Phase Change
        if not self.game_over:
            self.phase = 'move_duck'
    def place_duck(self, pos):
        """Finalizes the turn."""
        self.duck_pos = pos
        self.phase = 'move_piece'
        self.turn = 'b' if self.turn == 'w' else 'w'

    def ai_turn(self):
        """Basic AI for Black Player."""
        if self.game_over: return

        # Phase 1: Move Piece
        if self.phase == 'move_piece':
            all_moves = []
            # Gather all pieces
            for r in range(8):
                for c in range(8):
                    p = self.board[r][c]
                    if p and p.color == 'b':
                        moves = self.get_piece_legal_moves(r, c)
                        for m in moves:
                            all_moves.append(((r, c), m))

            if not all_moves:
                # No legal moves? Technically a stalemate or pass, but rare in Duck Chess.
                # We just skip turn to avoid crash.
                self.turn = 'w'
                return

            # Pick Random Move
            move = random.choice(all_moves)

            # Artificial delay for UX
            pygame.time.wait(500)
            self.execute_move(move[0], move[1])

        # Phase 2: Place Duck (if game didn't end)
        if self.phase == 'move_duck' and not self.game_over:
            empty_squares = []
            for r in range(8):
                for c in range(8):
                    if self.board[r][c] is None:
                        empty_squares.append((r, c))

            if empty_squares:
                duck_dest = random.choice(empty_squares)
                pygame.time.wait(300)
                self.place_duck(duck_dest)

    def draw_board(self):
        """Renders the graphical state."""
        self.screen.fill(BG_COLOR)

        for r in range(8):
            for c in range(8):
                x = c * SQUARE_SIZE
                y = r * SQUARE_SIZE

                # Draw Tile
                color = WHITE if (r + c) % 2 == 0 else BLACK_SQ
                pygame.draw.rect(self.screen, color, (x, y, SQUARE_SIZE, SQUARE_SIZE))

                # Highlight Selected
                if self.selected_square == (r, c):
                    pygame.draw.rect(self.screen, HIGHLIGHT, (x, y, SQUARE_SIZE, SQUARE_SIZE))

                # Highlight Duck
                if self.duck_pos == (r, c):
                    # Draw a water background for the duck (optional, looks nice)
                    pygame.draw.rect(self.screen, (135, 206, 235), (x, y, SQUARE_SIZE, SQUARE_SIZE))
                    self.draw_rubber_duck(r, c)

                # Highlight Valid Moves
                if (r, c) in self.valid_moves:
                    s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE))
                    s.set_alpha(100)  # Transparency
                    s.fill((0, 255, 0))  # Green
                    self.screen.blit(s, (x, y))

                # Draw Piece
                piece = self.board[r][c]
                if piece:
                    text = UNICODE_PIECES[piece.color][piece.type]
                    # Color check: Black pieces distinct from text color?
                    p_color = (0, 0, 0) if piece.color == 'b' else (255, 255, 255)
                    # Use a shadow/outline for visibility

                    # Render Glyph
                    txt_surf = self.font_large.render(text, True, p_color)

                    # Center text
                    rect = txt_surf.get_rect(center=(x + SQUARE_SIZE // 2, y + SQUARE_SIZE // 2))

                    # If white piece, add a black outline for contrast against white squares
                    if piece.color == 'w':
                        outline = self.font_large.render(text, True, (0, 0, 0))
                        outline_rect = outline.get_rect(center=(x + SQUARE_SIZE // 2 + 1, y + SQUARE_SIZE // 2 + 1))
                        self.screen.blit(outline, outline_rect)

                    self.screen.blit(txt_surf, rect)

    def draw_ui(self):
        """Draws game status text."""
        area = pygame.Rect(0, 800, SCREEN_WIDTH, 50)
        pygame.draw.rect(self.screen, (220, 220, 220), area)

        status_text = ""
        if self.game_over:
            winner_text = "White" if self.winner == 'w' else "Black"
            status_text = f"GAME OVER! {winner_text} Wins! (King Captured)"
        else:
            turn_text = "White's Turn" if self.turn == 'w' else "Black's Turn (AI)"
            phase_text = "Select/Move Piece" if self.phase == 'move_piece' else "Place the DUCK"
            status_text = f"{turn_text} | Phase: {phase_text}"

        txt = self.font_ui.render(status_text, True, TEXT_COLOR)
        self.screen.blit(txt, (20, 810))

    def run(self):
        running = True
        while running:
            # Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.turn == 'w':
                        self.handle_click(pygame.mouse.get_pos())

            # AI Logic
            if self.turn == 'b' and not self.game_over:
                self.ai_turn()

            # Drawing
            self.draw_board()
            self.draw_ui()
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = DuckChess()
    game.run()