#!/usr/bin/python3
import os
import time
import socket

import chess
import chess.engine
import chess.pgn

from config import *
import handle_masalot as masalot
import handle_stockfish as stockfish

def fen_match(fen1: str, fen2: str) -> bool:
    """
    Returns True if the first three parts of fen1 and fen2 match:
      1) Piece placement
      2) Side to move
      3) Castling rights
    Ignores en-passant, halfmove, and fullmove fields.
    """
    fen1_parts = fen1.split()
    fen2_parts = fen2.split()

    if len(fen1_parts) < 3 or len(fen2_parts) < 3:
        return False

    return (
        fen1_parts[0] == fen2_parts[0] and
        fen1_parts[1] == fen2_parts[1] and
        fen1_parts[2] == fen2_parts[2]
    )

def fen_to_uci(board: chess.Board, new_fen: str):
    for move in board.legal_moves:
        board.push(move)
        if fen_match(board.fen(), new_fen):
            board.pop()
            return move
        board.pop()
    return None

def communicate_with_masalot(s, fen):
    s.sendall(fen.encode('utf-8'))
    response = s.recv(1024).decode('utf-8')
    return response

def handle_game(masalot_white, game_index):
    """Plays one game between Masalot and Stockfish.
       Saves the resulting game in PGN format to PGN/game_{game_index}.pgn.
    """
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({
        "UCI_LimitStrength": True,
        "UCI_Elo": STOCKFISH_ELO_LIMIT
    })
    board = chess.Board()

    if not masalot_white:
        engine_move = engine.play(board, chess.engine.Limit(depth=STOCKFISH_DEPTH_LIMIT))
        board.push(engine_move.move)
        print("Stockfish first move:", engine_move.move)
        print(board)

    # Main game loop
    while not board.is_game_over():
        # 1) Masalot’s move in FEN
        masalot_move_fen = communicate_with_masalot(s, board.fen())
        print(masalot_move_fen)
        if len(masalot_move_fen) == 4:
            move = masalot_move_fen
            print(board.push_uci(move))
        else:
            move = fen_to_uci(board, masalot_move_fen)
            board.push(move)
        # board.set_fen(masalot_move_fen)
        print("Masalot's move:", move)
        print(board)

        if board.is_game_over():
            break

        # 2) Stockfish's move
        engine_move = engine.play(board, chess.engine.Limit(depth=STOCKFISH_DEPTH_LIMIT))
        board.push(engine_move.move)
        print("Stockfish's move:", engine_move.move)
        print(board)

    # Determine final game result
    if board.is_checkmate():
        # If it's checkmate, then board.turn is the side to move with no legal moves => they lost.
        if board.turn == chess.WHITE:
            # White to move but no moves => Black delivered mate
            masalot_score = 0 if masalot_white else 1
            stockfish_score = 1 if masalot_white else 0
        else:
            # Black to move but no moves => White delivered mate
            masalot_score = 1 if masalot_white else 0
            stockfish_score = 0 if masalot_white else 1
    else:
        # Otherwise it's a draw (stalemate, repetition, etc.)
        masalot_score = 0.5
        stockfish_score = 0.5

    engine.quit()

    # =======================
    # Save the Game to PGN
    # =======================
    # 1. Create the folder if it doesn't exist
    os.makedirs("PGN", exist_ok=True)

    # 2. Build a PGN object from the final board state
    game_pgn = chess.pgn.Game.from_board(board)

    # 3. Set some headers
    game_pgn.headers["Event"] = f"Masalot {MASALOT_CONFIG} vs Stockfish {STOCKFISH_ELO_LIMIT}"
    game_pgn.headers["Site"] = "Chess Arena"
    game_pgn.headers["Date"] = time.strftime("%Y.%m.%d", time.localtime())
    game_pgn.headers["Round"] = str(game_index)
    game_pgn.headers["White"] = "Masalot" if masalot_white else "Stockfish"
    game_pgn.headers["Black"] = "Stockfish" if masalot_white else "Masalot"

    # 4. Save to a file
    pgn_filename = f"PGN/game_{game_index + 1}.pgn"
    with open(pgn_filename, "w") as f:
        print(game_pgn, file=f, end="\n\n")

    return masalot_score, stockfish_score



if __name__ == "__main__":
    masalot_score = 0
    stockfish_score = 0
    masalot_white = True

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect(('localhost', CHESS_ENGINE_PORT))

        for i in range(NO_GAMES):
            m_score, sf_score = handle_game(masalot_white, i)
            masalot_score += m_score
            stockfish_score += sf_score
            masalot_white = not masalot_white
            print(f"Score fter game {i + 1}")
            print(f"Masalot {masalot_score} - {stockfish_score} Stockfish")
        
        print(f"Battle of {NO_GAMES} games has come to an end")
        if stockfish_score < masalot_score:
            print(f"Masalot WON!")
            print(f"Masalot {masalot_score} - {stockfish_score} Stockfish")

        elif stockfish_score > masalot_score:
            print(f"Stockfish WON!")
            print(f"Masalot {masalot_score} - {stockfish_score} Stockfish")
        else:
            print(f"DRAW!")
            print(f"Masalot {masalot_score} - {stockfish_score} Stockfish")
