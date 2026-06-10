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
# LEER TABLERO VÍA JAVASCRIPT
# Intenta múltiples formas de acceder al estado interno del juego
# =========================
JS_GET_BOARD = """
try {
    // Intento 1: objeto global GameManager (juego original)
    if (typeof GameManager !== 'undefined') {
        var gm = GameManager.instance || window.gameManager;
        if (gm && gm.grid && gm.grid.cells) {
            var cells = gm.grid.cells;
            var board = [];
            for (var r = 0; r < 4; r++) {
                var row = [];
                for (var c = 0; c < 4; c++) {
                    row.push(cells[c][r] ? cells[c][r].value : 0);
                }
                board.push(row);
            }
            return JSON.stringify({source: 'GameManager', board: board});
        }
    }

    // Intento 2: buscar en window cualquier objeto con grid/cells
    for (var key in window) {
        try {
            var obj = window[key];
            if (obj && obj.grid && obj.grid.cells) {
                var cells = obj.grid.cells;
                var board = [];
                for (var r = 0; r < 4; r++) {
                    var row = [];
                    for (var c = 0; c < 4; c++) {
                        row.push(cells[c][r] ? cells[c][r].value : 0);
                    }
                    board.push(row);
                }
                return JSON.stringify({source: key, board: board});
            }
        } catch(e) {}
    }

    // Intento 3: leer desde el DOM con clases tile-position
    var tiles = document.querySelectorAll('.tile');
    if (tiles.length > 0) {
        var board = [[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];
        tiles.forEach(function(tile) {
            var classes = tile.className.split(' ');
            var value = 0, row = -1, col = -1;
            classes.forEach(function(cls) {
                if (/^tile-\d+$/.test(cls)) value = parseInt(cls.replace('tile-',''));
                if (/^tile-position-\d+-\d+$/.test(cls)) {
                    var parts = cls.replace('tile-position-','').split('-');
                    col = parseInt(parts[0]) - 1;
                    row = parseInt(parts[1]) - 1;
                }
            });
            if (value > 0 && row >= 0 && col >= 0) {
                if (board[row][col] < value) board[row][col] = value;
            }
        });
        return JSON.stringify({source: 'DOM-tiles', board: board});
    }

    // Intento 4: leer texto visible de las celdas
    var cells = document.querySelectorAll('.grid-cell, [class*="cell"], [class*="tile"]');
    if (cells.length > 0) {
        var info = [];
        cells.forEach(function(c) {
            info.push({cls: c.className, txt: c.innerText});
        });
        return JSON.stringify({source: 'grid-cells-debug', cells: info.slice(0,20)});
    }

    // Intento 5: volcar estructura de window para debug
    var keys = Object.keys(window).filter(function(k) {
        try { return window[k] && typeof window[k] === 'object'; } catch(e) { return false; }
    }).slice(0, 30);
    return JSON.stringify({source: 'debug-window-keys', keys: keys});

} catch(e) {
    return JSON.stringify({source: 'error', msg: e.toString()});
}
"""

JS_IS_OVER = """
try {
    // Buscar mensaje de game over visible
    var msgs = document.querySelectorAll('.game-message, [class*="game-over"], [class*="gameover"]');
    for (var i = 0; i < msgs.length; i++) {
        var style = window.getComputedStyle(msgs[i]);
        if (style.display !== 'none' && style.visibility !== 'hidden') {
            var txt = msgs[i].innerText.toLowerCase();
            if (txt.includes('over') || txt.includes('try again') || txt.includes('game over')) {
                return true;
            }
        }
    }
    return false;
} catch(e) { return false; }
"""

def get_board():
    result = driver.execute_script(JS_GET_BOARD)
    if not result:
        return None, "sin resultado"
    import json
    data = json.loads(result)
    source = data.get("source", "?")
    if "board" in data:
        return data["board"], source
    return None, f"{source}: {data}"

def board_is_empty(board):
    return board is None or all(board[r][c] == 0 for r in range(4) for c in range(4))

def print_board(board):
    if not board:
        print("[tablero vacío]")
        return
    print("\n+" + "------+" * 4)
    for row in board:
        print("|" + "|".join(f"{v:^6}" if v else "      " for v in row) + "|")
    print("+" + "------+" * 4)

# =========================
# LÓGICA DE SIMULACIÓN
# =========================
def slide_row_left(row):
    tiles = [x for x in row if x != 0]
    merged, skip = [], False
    for i in range(len(tiles)):
        if skip: skip = False; continue
        if i + 1 < len(tiles) and tiles[i] == tiles[i+1]:
            merged.append(tiles[i] * 2); skip = True
        else:
            merged.append(tiles[i])
    return merged + [0] * (4 - len(merged))

def move_left(b):  return [slide_row_left(row) for row in b]
def move_right(b): return [slide_row_left(row[::-1])[::-1] for row in b]
def transpose(b):  return [[b[r][c] for r in range(4)] for c in range(4)]
def move_up(b):    return transpose(move_left(transpose(b)))
def move_down(b):  return transpose(move_right(transpose(b)))

def board_changed(b1, b2):
    return any(b1[r][c] != b2[r][c] for r in range(4) for c in range(4))

def get_empty_cells(board):
    return [(r, c) for r in range(4) for c in range(4) if board[r][c] == 0]

# =========================
# HEURÍSTICAS + EXPECTIMAX
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
    score += len(get_empty_cells(board)) * 1500
    for row in board:
        nz = [x for x in row if x]
        for i in range(len(nz)-1):
            if nz[i] < nz[i+1]: score -= nz[i+1] * 2
    for c in range(4):
        col = [board[r][c] for r in range(4) if board[r][c]]
        for i in range(len(col)-1):
            if col[i] < col[i+1]: score -= col[i+1] * 2
    for r in range(4):
        for c in range(4):
            if board[r][c]:
                for dr, dc in [(0,1),(1,0)]:
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < 4 and 0 <= nc < 4 and board[nr][nc]:
                        score -= abs(board[r][c] - board[nr][nc])
    return score

MOVES = {"UP": move_up, "DOWN": move_down, "LEFT": move_left, "RIGHT": move_right}
MOVE_KEYS = {"UP": Keys.UP, "DOWN": Keys.DOWN, "LEFT": Keys.LEFT, "RIGHT": Keys.RIGHT}

def expectimax(board, depth, is_player):
    if depth == 0: return score_board(board)
    if is_player:
        best = float("-inf")
        for fn in MOVES.values():
            nb = fn(board)
            if board_changed(board, nb):
                best = max(best, expectimax(nb, depth-1, False))
        return best if best != float("-inf") else score_board(board)
    else:
        empty = get_empty_cells(board)
        if not empty: return score_board(board)
        sampled = random.sample(empty, min(len(empty), 4))
        total = sum(
            prob * expectimax([row[:] for row in board], depth-1, True)
            for r, c in sampled
            for val, prob in [(2, 0.9), (4, 0.1)]
            if not [board.__setitem__(0, board[0])] or True  # side-effect-free
            for board in [[r2[:] for r2 in board]]
            if not board[r].__setitem__(c, val) or True
        )
        # Versión limpia sin list comprehension trick:
        total2 = 0
        for r, c in sampled:
            for val, prob in [(2, 0.9), (4, 0.1)]:
                nb = [row[:] for row in board]
                nb[r][c] = val
                total2 += prob * expectimax(nb, depth-1, True)
        return total2 / len(sampled)

def best_move(board, depth=3):
    best_score, best_dir = float("-inf"), None
    for direction, fn in MOVES.items():
        nb = fn(board)
        if board_changed(board, nb):
            val = expectimax(nb, depth-1, False)
            if val > best_score:
                best_score, best_dir = val, direction
    return best_dir

def has_won(board):
    return board and any(board[r][c] >= 2048 for r in range(4) for c in range(4))

def max_tile(board):
    if not board: return 0
    return max(board[r][c] for r in range(4) for c in range(4))

# =========================
# BUCLE PRINCIPAL
# =========================
try:
    print("Abriendo play2048.co ...")
    driver.get("https://play2048.co/")
    time.sleep(4)

    body = driver.find_element(By.TAG_NAME, "body")
    body.click()
    time.sleep(1)

    # Diagnóstico inicial
    board, source = get_board()
    print(f"Fuente de lectura: {source}")
    if board:
        print_board(board)
    else:
        print(f"No se pudo leer el tablero: {source}")
        print("Revisa el output de debug arriba para ajustar el script.")

    print("\nIniciando bot...\n")

    move_count = 0
    last_print = 0
    empty_streak = 0
    FALLBACK = [Keys.LEFT, Keys.UP, Keys.RIGHT, Keys.DOWN]

    while True:
        board, source = get_board()

        if board_is_empty(board):
            empty_streak += 1
            if empty_streak % 10 == 1:
                print(f"[!] No se lee el tablero (intento {empty_streak}). Fuente: {source}")
            body.send_keys(FALLBACK[move_count % 4])
            move_count += 1
            time.sleep(0.15)
            continue

        empty_streak = 0

        if move_count - last_print >= 50:
            print_board(board)
            print(f"Movimientos: {move_count} | Max tile: {max_tile(board)} | Fuente: {source}")
            last_print = move_count

        if has_won(board):
            print("\n¡VICTORIA! Tile 2048 alcanzado!")
            print_board(board)
            break

        if driver.execute_script(JS_IS_OVER):
            print(f"\nGame Over tras {move_count} movimientos. Max: {max_tile(board)}")
            print_board(board)
            break

        direction = best_move(board, depth=3)
        key = MOVE_KEYS[direction] if direction else FALLBACK[move_count % 4]
        body.send_keys(key)
        move_count += 1
        time.sleep(0.05)

except Exception as e:
    print(f"Error: {e}")
    import traceback; traceback.print_exc()
finally:
    time.sleep(4)
    driver.quit()