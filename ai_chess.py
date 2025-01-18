import pygame
import sys
import chess
import os
import requests
import re
import time
import random
from openai import OpenAI

##############################################################################
# KEYS AND MODELS (UNCHANGED)
##############################################################################
client = OpenAI(api_key="[CHATGPT API KEY HERE]")
CHATGPT_MODEL = "gpt-4o-mini"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-1.5-flash:generateContent?key=GEMINIAPIKEYHERE"
)
GEMINI_HEADERS = {"Content-Type": "application/json"}

##############################################################################
# PYGAME CONSTANTS
##############################################################################
TILE_SIZE = 80
BOARD_SIZE = TILE_SIZE * 8
FPS = 30

LIGHT_COLOR = (238, 238, 210)
DARK_COLOR = (118, 150, 86)
HIGHLIGHT_COLOR = (186, 202, 43)

FONT_COLOR = (255, 255, 0)  # bright yellow
BACKGROUND_COLOR = (0, 0, 0) # black

##############################################################################
# IMAGE LOADING
##############################################################################

PIECE_IMAGES = {}

def load_piece_images():
    """Loads piece images from a local 'images' folder into PIECE_IMAGES."""
    pieces = ['P','N','B','R','Q','K']
    colors = ['w','b']
    for color in colors:
        for piece in pieces:
            filename = f"{color}{piece}.png"
            path = os.path.join("images", filename)
            if os.path.exists(path):
                img = pygame.image.load(path)
                PIECE_IMAGES[color + piece] = pygame.transform.scale(img, (TILE_SIZE, TILE_SIZE))

##############################################################################
# DRAWING / UI
##############################################################################

def draw_board(
    screen, board, font, label_white, label_black,
    is_chatgpt_turn, chatgpt_is_white, selected_square=None
):
    """
    Draw:
     - The chessboard squares
     - The pieces
     - Top labels: White/Black
     - Material-based score (bottom-left)
     - Whose turn it is (bottom-right)
    """
    # Draw squares
    for rank in range(8):
        for file in range(8):
            square_color = LIGHT_COLOR if (rank + file) % 2 == 0 else DARK_COLOR
            rect = (file * TILE_SIZE, rank * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(screen, square_color, rect)

    # Highlight selected square
    if selected_square is not None:
        sel_file = selected_square % 8
        sel_rank = 7 - (selected_square // 8)
        highlight_rect = (sel_file * TILE_SIZE, sel_rank * TILE_SIZE, TILE_SIZE, TILE_SIZE)
        pygame.draw.rect(screen, HIGHLIGHT_COLOR, highlight_rect)

    # Draw pieces
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            file = square % 8
            rank = 7 - (square // 8)
            piece_str = ('w' if piece.color == chess.WHITE else 'b') + piece.symbol().upper()
            if piece_str in PIECE_IMAGES:
                screen.blit(PIECE_IMAGES[piece_str], (file * TILE_SIZE, rank * TILE_SIZE))

    # Labels for White/Black
    label_w = font.render(label_white, True, FONT_COLOR, BACKGROUND_COLOR)
    label_b = font.render(label_black, True, FONT_COLOR, BACKGROUND_COLOR)
    screen.blit(label_w, (10, 10))
    screen.blit(label_b, (BOARD_SIZE - label_b.get_width() - 10, 10))

    # Material-based score
    score_str = material_score_string(board)
    label_score = font.render(score_str, True, FONT_COLOR, BACKGROUND_COLOR)
    screen.blit(label_score, (10, BOARD_SIZE - label_score.get_height() - 10))

    # Whose turn is it? (bottom right corner)
    # If chatgpt_is_white is True and is_chatgpt_turn is True => "White: ChatGPT" turn
    # Otherwise if chatgpt_is_white is False and is_chatgpt_turn is False => "White: Gemini" turn
    if is_chatgpt_turn:
        # ChatGPT is the mover
        if chatgpt_is_white:
            turn_label_text = "White to move (ChatGPT)"
        else:
            turn_label_text = "Black to move (ChatGPT)"
    else:
        # Gemini is the mover
        if chatgpt_is_white:
            turn_label_text = "Black to move (Gemini)"
        else:
            turn_label_text = "White to move (Gemini)"

    label_turn = font.render(turn_label_text, True, FONT_COLOR, BACKGROUND_COLOR)
    screen.blit(label_turn, (BOARD_SIZE - label_turn.get_width() - 10, BOARD_SIZE - label_turn.get_height() - 10))

##############################################################################
# SCORING
##############################################################################

def material_score(board):
    """Returns an integer: positive if White is ahead, negative if Black is ahead."""
    score = 0
    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9
    }
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece:
            val = piece_values.get(piece.piece_type, 0)
            if piece.color == chess.WHITE:
                score += val
            else:
                score -= val
    return score

def material_score_string(board):
    score = material_score(board)
    if score > 0:
        return f"White leads by {score}"
    elif score < 0:
        return f"Black leads by {-score}"
    else:
        return "Scores are even"

def determine_winner(board, chatgpt_is_white):
    """Determine the winner based on material score and player roles."""
    score = material_score(board)
    if score > 0:
        winner = "ChatGPT" if chatgpt_is_white else "Gemini"
        return f"White wins ({winner})"
    elif score < 0:
        winner = "Gemini" if chatgpt_is_white else "ChatGPT"
        return f"Black wins ({winner})"
    else:
        return "It's a tie"


##############################################################################
# AI / PROMPTS / MOVE LOGIC
##############################################################################

def list_legal_moves(board):
    return ", ".join(move.uci() for move in board.legal_moves)

def extract_move(text, board):
    """Attempts to parse UCI or SAN from text."""
    # UCI pattern
    uci_match = re.search(r"\b([a-h][1-8])([a-h][1-8])([qrbnQRBN])?\b", text)
    if uci_match:
        return "".join(g for g in uci_match.groups() if g)

    # SAN pattern
    san_match = re.search(r"\b([KQRNB]?[a-h]?[1-8]?x?[a-h][1-8](=[QRNB])?\+?#?)\b", text)
    if san_match:
        possible_san = san_match.group(0)
        try:
            move = board.parse_san(possible_san)
            return move.uci()
        except:
            pass
    return None

def get_chatgpt_move_raw(board, gemini_move):
    """
    Queries ChatGPT for raw text representing a chess move,
    with debugging info to console.
    """
    legal_moves_str = list_legal_moves(board)
    print(f"[DEBUG] ChatGPT: legal moves => {legal_moves_str}")
    print(f"[DEBUG] ChatGPT: FEN => {board.fen()}")
    print(f"[DEBUG] Gemini's last move => {gemini_move}")

    system_prompt = (
        "You are ChatGPT, the MIGHTY AI SUPERCOMPUTER with one goal: "
        "defeat Google's supercomputer in chess. Reply ONLY with the next move "
        "in valid UCI notation or standard algebraic notation (e.g., Nf6). "
        "No extra text."
        "You may not repeat moves!"
    )
    user_prompt = (
        "You must pick exactly one legal move from this list:\n"
        f"{legal_moves_str}\n\n"
        f"The current board state (FEN) is:\n{board.fen()}\n"
        f"Gemini's last move was: {gemini_move}\n"
        "If you propose a move not in the list above, it is illegal. "
        "Return your next move now."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        completion = client.chat.completions.create(
            model=CHATGPT_MODEL,
            messages=messages,
            temperature=0.4
        )
        raw_response = completion.choices[0].message.content.strip()
        print(f"[DEBUG] ChatGPT raw response => {raw_response}")
        return raw_response
    except Exception as e:
        print("[DEBUG] ChatGPT connection error:", e)
        return None

def retry_chatgpt_move(board, gemini_move, max_retries=100):
    """Get ChatGPT's valid move with up to max_retries, debug info each attempt."""
    for attempt in range(1, max_retries+1):
        print(f"[DEBUG] ChatGPT attempt {attempt} of {max_retries}")
        raw_text = get_chatgpt_move_raw(board, gemini_move if gemini_move else "None")
        if raw_text:
            move_str = extract_move(raw_text, board)
            if move_str:
                move_obj = chess.Move.from_uci(move_str)
                if move_obj in board.legal_moves:
                    print(f"[DEBUG] ChatGPT => valid move found: {move_str}")
                    return move_str
                else:
                    print(f"[DEBUG] ChatGPT => invalid move: {move_str}")
            else:
                print("[DEBUG] ChatGPT => no move extracted.")
    print("[DEBUG] ChatGPT => gave up after max retries.")
    return None

##############################################################################
# "Gemini is thinking" LOGIC
##############################################################################
def draw_thinking(screen, font, thinking_text):
    """
    Draws 'thinking_text' in the center of the board, in bright yellow on black.
    We flip the display so it shows immediately.
    """
    # Render the text
    label = font.render(thinking_text, True, FONT_COLOR, BACKGROUND_COLOR)
    x = (BOARD_SIZE - label.get_width()) // 2
    y = (BOARD_SIZE - label.get_height()) // 2
    screen.blit(label, (x, y))
    pygame.display.flip()


def get_gemini_move_raw(board, chatgpt_move, screen=None, font=None):
    """
    Queries Gemini for raw text representing a chess move,
    plus debug info and "Gemini is thinking" on HTTP 429.
    """
    legal_moves_str = list_legal_moves(board)
    print(f"[DEBUG] Gemini: legal moves => {legal_moves_str}")
    print(f"[DEBUG] Gemini: FEN => {board.fen()}")
    print(f"[DEBUG] ChatGPT's last move => {chatgpt_move}")

    prompt = (
        "You are Gemini, an AI-powered supercomputer by Google, playing chess against ChatGPT. "
        "Respond ONLY with your next move in strictly valid UCI notation (e.g., e2e4), or if "
        "needed, in standard algebraic notation (like Nf6). Absolutely no extra text.\n"
        "You may not repeat moves!"
        "You must pick exactly one legal move from this list:\n"
        f"{legal_moves_str}\n\n"
        f"The current board state (FEN) is: {board.fen()}\n"
        f"ChatGPT's last move was: {chatgpt_move}\n"
        "If you propose a move not in the list above, it is illegal. "
        "Return your next move now."
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        # Optional small delay
        time.sleep(4)
        response = requests.post(GEMINI_URL, headers=GEMINI_HEADERS, json=payload)
        if response.status_code == 200:
            data = response.json()
            raw_response = (
                data.get("candidates", [])[0]
                .get("content", {})
                .get("parts", [])[0]
                .get("text", "")
                .strip()
            )
            print(f"[DEBUG] Gemini raw response => {raw_response}")
            return raw_response
        else:
            print(f"[DEBUG] Gemini responded HTTP {response.status_code}")
            # If we specifically see 429, show "Gemini is thinking" on screen
            if response.status_code == 429 and screen and font:
                draw_thinking(screen, font, "Gemini is thinking...")
            print("[DEBUG] waiting 10s due to error code")
            time.sleep(60) #max number of requests per minute reached
    except Exception as e:
        print("[DEBUG] Gemini connection error:", e)
    return None

def retry_gemini_move(board, chatgpt_move, screen=None, font=None, max_retries=100):
    """Get Gemini's valid move with up to max_retries, debug info each attempt."""
    for attempt in range(1, max_retries+1):
        print(f"[DEBUG] Gemini attempt {attempt} of {max_retries}")
        raw_text = get_gemini_move_raw(board, chatgpt_move if chatgpt_move else "None", screen, font)
        if raw_text:
            move_str = extract_move(raw_text, board)
            if move_str:
                move_obj = chess.Move.from_uci(move_str)
                if move_obj in board.legal_moves:
                    print(f"[DEBUG] Gemini => valid move found: {move_str}")
                    return move_str
                else:
                    print(f"[DEBUG] Gemini => invalid move: {move_str}")
            else:
                print("[DEBUG] Gemini => no move extracted.")
    print("[DEBUG] Gemini => gave up after max retries.")
    return None

##############################################################################
# MAIN GAME LOOP
##############################################################################
def main():
    pygame.init()
    screen = pygame.display.set_mode((BOARD_SIZE, BOARD_SIZE))
    pygame.display.set_caption("Chess UI Demo (ChatGPT vs. Gemini)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 20)

    load_piece_images()

    board = chess.Board()
    selected_square = None

    # Randomly assign white/black
    chatgpt_is_white = bool(random.getrandbits(1))
    if chatgpt_is_white:
        white_label = "White: ChatGPT"
        black_label = "Black: Gemini"
        is_chatgpt_turn = True
    else:
        white_label = "White: Gemini"
        black_label = "Black: ChatGPT"
        is_chatgpt_turn = False

    chatgpt_last_move = None
    gemini_last_move = None
    running = True

    # Record the start time
    start_time = time.time()

    while running:
        clock.tick(FPS)

        # Check for game over
        if board.is_game_over():
            running = False
            break

        # Handle turns
        if (chatgpt_is_white and is_chatgpt_turn) or (not chatgpt_is_white and not is_chatgpt_turn):
            # ChatGPT's turn
            move_str = retry_chatgpt_move(board, gemini_last_move)
            if move_str:
                board.push_uci(move_str)
                chatgpt_last_move = move_str
            else:
                print("[DEBUG] ChatGPT => no valid move found. Ending game.")
                running = False
        else:
            # Gemini's turn
            move_str = retry_gemini_move(board, chatgpt_last_move, screen, font)
            if move_str:
                board.push_uci(move_str)
                gemini_last_move = move_str
            else:
                print("[DEBUG] Gemini => no valid move found. Ending game.")
                running = False

        is_chatgpt_turn = not is_chatgpt_turn

        # Handle user input
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        # Draw
        screen.fill((0, 0, 0))
        draw_board(
            screen, board, font,
            label_white=white_label,
            label_black=black_label,
            is_chatgpt_turn=is_chatgpt_turn,
            chatgpt_is_white=chatgpt_is_white,
            selected_square=selected_square
        )
        pygame.display.flip()

    # Record the end time
    end_time = time.time()
    elapsed_time = end_time - start_time

    # Determine winner and print result
    winner = determine_winner(board, chatgpt_is_white)
    print("\nGame Over.")
    print("Final FEN:", board.fen())
    print("Result:", winner)
    print(f"Elapsed Time: {elapsed_time:.2f} seconds")

    pygame.quit()
    return winner, elapsed_time

if __name__ == "__main__":
    result, game_time = main()
    print("Winner:", result)
    print(f"Game Duration: {game_time:.2f} seconds")