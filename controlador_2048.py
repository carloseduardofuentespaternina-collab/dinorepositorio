import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager


# =========================
# CONFIGURACIÓN CHROME
# =========================
chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)


# =========================
# LEER EL TABLERO DESDE EL DOM
# =========================
def get_board():
    """Lee el estado actual del tablero (4x4) desde el DOM."""
    board = [[0] * 4 for _ in range(4)]
    tiles = driver.find_elements(By.CSS_SELECTOR, ".tile")
    for tile in tiles:
        classes = tile.get_attribute("class").split()
        value = 0
        row = col = 0
        for cls in classes:
            if cls.startswith("tile-") and cls[5:].isdigit():
                value = int(cls[5:])
            if cls.startswith("tile-position-"):
                parts = cls.replace("tile-position-", "").split("-")
                if len(parts) == 2:
                    col = int(parts[0]) - 1  # 1-indexed → 0-indexed
                    row = int(parts[1]) - 1
        if value > 0 and 0 <= row < 4 and 0 <= col < 4:
            board[row][col] = value
    return board


def print_board(board):
    print("\n+" + "------+" * 4)
    for row in board:
        print("|" + "|".join(f"{v:^6}" if v else "      " for v in row) + "|")
        print("+" + "------+" * 4)


# =========================
# LÓGICA DE SIMULACIÓN DE MOVIMIENTOS
# =========================
def slide_row_left(row):
    """Desliza y fusiona una fila hacia la izquierda."""
    tiles = [x for x in row if x != 0]
    merged = []
    skip = False
    for i in range(len(tiles)):
        if skip:
            skip = False
            continue
        if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
            merged.append(tiles[i] * 2)
            skip = True
        else:
            merged.append(tiles[i])
    merged += [0] * (4 - len(merged))
    return merged


def move_left(board):
    return [slide_row_left(row) for row in board]


def move_right(board):
    return [slide_row_left(row[::-1])[::-1] for row in board]


def transpose(board):
    return [[board[r][c] for r in range(4)] for c in range(4)]


def move_up(board):
    return transpose(move_left(transpose(board)))


def move_down(board):
    return transpose(move_right(transpose(board)))


def board_changed(b1, b2):
    return any(b1[r][c] != b2[r][c] for r in range(4) for c in range(4))


def get_empty_cells(board):
    return [(r, c) for r in range(4) for c in range(4) if board[r][c] == 0]


def add_random_tile(board):
    empty = get_empty_cells(board)
    if empty:
        r, c = random.choice(empty)
        board[r][c] = 4 if random.random() < 0.1 else 2
    return board


# =========================
# HEURÍSTICAS DE PUNTUACIÓN
# =========================

# Pesos para la esquina inferior-izquierda (snake pattern)
WEIGHT_MATRIX = [
    [2**15, 2**14, 2**13, 2**12],
    [2**8,  2**9,  2**10, 2**11],
    [2**7,  2**6,  2**5,  2**4],
    [2**0,  2**1,  2**2,  2**3],
]


def score_board(board):
    """Puntúa el tablero combinando múltiples heurísticas."""
    score = 0

    # 1. Snake weight: recompensa tener tiles grandes en posiciones de alto peso
    for r in range(4):
        for c in range(4):
            score += board[r][c] * WEIGHT_MATRIX[r][c]

    # 2. Celdas vacías: más celdas libres = más maniobra
    empty = len(get_empty_cells(board))
    score += empty * 1000

    # 3. Monotonía: penaliza filas/columnas que no son monótonas
    for row in board:
        non_zero = [x for x in row if x]
        for i in range(len(non_zero) - 1):
            if non_zero[i] < non_zero[i + 1]:
                score -= non_zero[i + 1]

    for c in range(4):
        col = [board[r][c] for r in range(4) if board[r][c]]
        for i in range(len(col) - 1):
            if col[i] < col[i + 1]:
                score -= col[i + 1]

    # 4. Suavidad: penaliza diferencias grandes entre tiles adyacentes
    for r in range(4):
        for c in range(4):
            if board[r][c]:
                for dr, dc in [(0, 1), (1, 0)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 4 and 0 <= nc < 4 and board[nr][nc]:
                        score -= abs(board[r][c] - board[nr][nc])

    return score


# =========================
# EXPECTIMAX (profundidad 3)
# =========================
MOVES = {
    "UP":    move_up,
    "DOWN":  move_down,
    "LEFT":  move_left,
    "RIGHT": move_right,
}

MOVE_KEYS = {
    "UP":    Keys.UP,
    "DOWN":  Keys.DOWN,
    "LEFT":  Keys.LEFT,
    "RIGHT": Keys.RIGHT,
}


def expectimax(board, depth, is_player):
    if depth == 0:
        return score_board(board)

    if is_player:
        best = float("-inf")
        for fn in MOVES.values():
            new_board = fn(board)
            if board_changed(board, new_board):
                val = expectimax(new_board, depth - 1, False)
                best = max(best, val)
        return best if best != float("-inf") else score_board(board)

    else:  # Nodo de azar (aparece tile 2 o 4 en celda vacía)
        empty = get_empty_cells(board)
        if not empty:
            return score_board(board)
        total = 0
        # Para eficiencia, muestreamos hasta 4 celdas vacías aleatoriamente
        sampled = random.sample(empty, min(len(empty), 4))
        for r, c in sampled:
            for val, prob in [(2, 0.9), (4, 0.1)]:
                new_board = [row[:] for row in board]
                new_board[r][c] = val
                total += prob * expectimax(new_board, depth - 1, True)
        return total / len(sampled)


def best_move(board, depth=3):
    """Elige el mejor movimiento usando Expectimax."""
    best_score = float("-inf")
    best_dir = None
    # Orden de preferencia por defecto si empatan
    for direction, fn in MOVES.items():
        new_board = fn(board)
        if board_changed(board, new_board):
            val = expectimax(new_board, depth - 1, False)
            if val > best_score:
                best_score = val
                best_dir = direction
    return best_dir


# =========================
# DETECCIÓN DE VICTORIA / DERROTA
# =========================
def has_won(board):
    return any(board[r][c] >= 2048 for r in range(4) for c in range(4))


def is_game_over_dom():
    elements = driver.find_elements(
        By.CSS_SELECTOR, ".game-message.game-over"
    )
    return bool(elements and elements[0].is_displayed())


def max_tile(board):
    return max(board[r][c] for r in range(4) for c in range(4))


# =========================
# BUCLE PRINCIPAL
# =========================
try:
    print("🚀 Abriendo 2048...")
    driver.get("https://play2048.co/")
    time.sleep(3)

    body = driver.find_element(By.TAG_NAME, "body")
    body.click()
    time.sleep(0.5)

    print("🎮 Juego iniciado — usando estrategia Expectimax + Corner\n")

    move_count = 0
    last_print = 0
    depth = 3  # Aumentar a 4 para más inteligencia (más lento)

    while True:
        board = get_board()

        if move_count - last_print >= 50:
            print_board(board)
            print(f"Movimientos: {move_count} | Tile máximo: {max_tile(board)}")
            last_print = move_count

        if has_won(board):
            print("\n🏆 ¡VICTORIA! Se alcanzó el tile 2048!")
            print_board(board)
            break

        if is_game_over_dom():
            print(f"\n💀 Game Over tras {move_count} movimientos.")
            print(f"   Tile máximo alcanzado: {max_tile(board)}")
            print_board(board)
            break

        direction = best_move(board, depth=depth)

        if direction is None:
            print("⚠️  No hay movimientos válidos.")
            break

        body.send_keys(MOVE_KEYS[direction])
        move_count += 1
        time.sleep(0.05)  # Pequeña pausa para que el DOM se actualice

    print("\nProceso finalizado.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    time.sleep(4)
    driver.quit()