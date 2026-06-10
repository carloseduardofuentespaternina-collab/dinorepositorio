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
# DIAGNÓSTICO: ver clases reales del DOM
# =========================
def debug_tiles():
    tiles = driver.find_elements(By.CSS_SELECTOR, ".tile")
    print(f"\n[DEBUG] Tiles encontrados: {len(tiles)}")
    for t in tiles:
        print("  →", t.get_attribute("class"))


# =========================
# LEER EL TABLERO DESDE EL DOM
# Soporta ambos formatos:
#   tile-position-COL-ROW  (formato clásico play2048.co)
#   tile-position-ROW-COL  (algunos forks)
# =========================
def get_board():
    board = [[0] * 4 for _ in range(4)]
    tiles = driver.find_elements(By.CSS_SELECTOR, ".tile")

    for tile in tiles:
        classes = tile.get_attribute("class").split()
        value = 0
        row = col = -1

        for cls in classes:
            # Valor: tile-2, tile-4, tile-16, tile-1024...
            if cls.startswith("tile-") and cls[5:].isdigit():
                value = int(cls[5:])
            # Posición: tile-position-C-R
            if cls.startswith("tile-position-"):
                parts = cls.replace("tile-position-", "").split("-")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    col = int(parts[0]) - 1  # columna (1-based → 0-based)
                    row = int(parts[1]) - 1  # fila    (1-based → 0-based)

        if value > 0 and 0 <= row < 4 and 0 <= col < 4:
            # Si ya hay un valor mayor en esa celda (tile fusionado), conservarlo
            if board[row][col] < value:
                board[row][col] = value

    return board


def board_is_empty(board):
    return all(board[r][c] == 0 for r in range(4) for c in range(4))


def print_board(board):
    print("\n+" + "------+" * 4)
    for row in board:
        print("|" + "|".join(f"{v:^6}" if v else "      " for v in row) + "|")
    print("+" + "------+" * 4)


# =========================
# LÓGICA DE SIMULACIÓN
# =========================
def slide_row_left(row):
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


# =========================
# HEURÍSTICAS
# =========================
WEIGHT_MATRIX = [
    [2**15, 2**14, 2**13, 2**12],
    [2**8,  2**9,  2**10, 2**11],
    [2**7,  2**6,  2**5,  2**4],
    [2**0,  2**1,  2**2,  2**3],
]

def score_board(board):
    score = 0
    for r in range(4):
        for c in range(4):
            score += board[r][c] * WEIGHT_MATRIX[r][c]
    empty = len(get_empty_cells(board))
    score += empty * 1500
    for row in board:
        non_zero = [x for x in row if x]
        for i in range(len(non_zero) - 1):
            if non_zero[i] < non_zero[i + 1]:
                score -= non_zero[i + 1] * 2
    for c in range(4):
        col = [board[r][c] for r in range(4) if board[r][c]]
        for i in range(len(col) - 1):
            if col[i] < col[i + 1]:
                score -= col[i + 1] * 2
    for r in range(4):
        for c in range(4):
            if board[r][c]:
                for dr, dc in [(0, 1), (1, 0)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 4 and 0 <= nc < 4 and board[nr][nc]:
                        score -= abs(board[r][c] - board[nr][nc])
    return score


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
    else:
        empty = get_empty_cells(board)
        if not empty:
            return score_board(board)
        sampled = random.sample(empty, min(len(empty), 4))
        total = 0
        for r, c in sampled:
            for val, prob in [(2, 0.9), (4, 0.1)]:
                new_board = [row[:] for row in board]
                new_board[r][c] = val
                total += prob * expectimax(new_board, depth - 1, True)
        return total / len(sampled)


def best_move(board, depth=3):
    best_score = float("-inf")
    best_dir = None
    for direction, fn in MOVES.items():
        new_board = fn(board)
        if board_changed(board, new_board):
            val = expectimax(new_board, depth - 1, False)
            if val > best_score:
                best_score = val
                best_dir = direction
    return best_dir


# =========================
# FALLBACK: estrategia simple si no puede leer el tablero
# =========================
FALLBACK_SEQUENCE = [Keys.LEFT, Keys.UP, Keys.RIGHT, Keys.DOWN]

def fallback_move(i):
    """Estrategia de esquina cuando el DOM no se puede leer."""
    # Preferencia: LEFT > UP > RIGHT > DOWN (mantiene tiles a la izquierda-arriba)
    return FALLBACK_SEQUENCE[i % len(FALLBACK_SEQUENCE)]


# =========================
# DETECCIÓN DE FIN DE JUEGO
# =========================
def has_won(board):
    return any(board[r][c] >= 2048 for r in range(4) for c in range(4))

def is_game_over_dom():
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, ".game-message.game-over")
        return bool(elements and elements[0].is_displayed())
    except:
        return False

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

    # --- DIAGNÓSTICO INICIAL ---
    debug_tiles()

    print("\n🎮 Juego iniciado — Expectimax + Corner Strategy\n")

    move_count = 0
    last_print = 0
    empty_reads = 0       # contador de lecturas vacías consecutivas
    depth = 3

    while True:
        board = get_board()

        # ¿El tablero está vacío? (problema de lectura DOM)
        if board_is_empty(board):
            empty_reads += 1
            if empty_reads <= 3 and move_count == 0:
                # Al inicio, esperamos un poco más
                time.sleep(0.5)
                continue
            # Usar fallback
            key = fallback_move(move_count)
            body.send_keys(key)
            move_count += 1
            time.sleep(0.1)
            if empty_reads % 20 == 1:
                print(f"⚠️  No se puede leer el tablero (mov {move_count}), usando fallback...")
                debug_tiles()
            continue
        else:
            empty_reads = 0

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
            print(f"   Tile máximo: {max_tile(board)}")
            print_board(board)
            break

        direction = best_move(board, depth=depth)

        if direction is None:
            # No hay movimiento válido según la simulación
            print("⚠️  Expectimax sin movimiento válido, usando fallback.")
            key = fallback_move(move_count)
            body.send_keys(key)
        else:
            body.send_keys(MOVE_KEYS[direction])

        move_count += 1
        time.sleep(0.05)

    print("\nProceso finalizado.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    time.sleep(4)
    driver.quit()