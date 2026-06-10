import time
import random
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# =========================
# OBTENER HTML LOCAL
# =========================
GAME_URL = "https://raw.githubusercontent.com/gabrielecirulli/2048/master/index.html"

def get_local_game_html():
    try:
        response = requests.get(GAME_URL, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# =========================
# CONFIGURACIÓN CHROME
# =========================
chrome_options = Options()
chrome_options.add_argument("--headless")  # Comentar para ver ventana
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1024,768")

# =========================
# OBTENER TABLERO CON JS
# =========================
def get_board_js(driver):
    script = """
        var board = [[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];
        var tiles = document.getElementsByClassName('tile');
        for (var i = 0; i < tiles.length; i++) {
            var tile = tiles[i];
            var value = parseInt(tile.innerText);
            var classes = tile.className;
            var match = classes.match(/tile-position-(\\d+)-(\\d+)/);
            if (match) {
                var row = parseInt(match[1]) - 1;
                var col = parseInt(match[2]) - 1;
                if (row >= 0 && row < 4 && col >= 0 && col < 4) {
                    board[row][col] = Math.max(board[row][col], value);
                }
            }
        }
        return board;
    """
    return driver.execute_script(script)

# =========================
# FUNCIONES DE MOVIMIENTO (SIMULACIÓN)
# =========================
def compress(row):
    new = [v for v in row if v != 0]
    new += [0] * (4 - len(new))
    return new

def merge(row):
    for i in range(3):
        if row[i] == row[i+1] and row[i] != 0:
            row[i] *= 2
            row[i+1] = 0
    return row

def move_row_left(row):
    row = compress(row[:])
    row = merge(row)
    row = compress(row)
    return row

def move_board_left(board):
    return [move_row_left(row) for row in board]

def move_board_right(board):
    return [move_row_left(row[::-1])[::-1] for row in board]

def transpose(board):
    return [list(row) for row in zip(*board)]

def move_board_up(board):
    t = transpose(board)
    moved = move_board_left(t)
    return transpose(moved)

def move_board_down(board):
    t = transpose(board)
    moved = move_board_right(t)
    return transpose(moved)

def simulate_move(board, direction):
    if direction == "UP":
        return move_board_up(board)
    elif direction == "DOWN":
        return move_board_down(board)
    elif direction == "LEFT":
        return move_board_left(board)
    elif direction == "RIGHT":
        return move_board_right(board)
    return board

# =========================
# HEURÍSTICA SIMPLE PERO EFECTIVA
# =========================
def heuristic_score(board):
    empty = sum(row.count(0) for row in board)
    max_tile = max(max(row) for row in board)
    # Bonificación por esquina superior izquierda
    corner = board[0][0] * 2
    # Penalizar fichas lejos de la esquina
    penalty = 0
    for r in range(4):
        for c in range(4):
            if board[r][c] > 0:
                penalty += board[r][c] * (r + c)
    # Recompensa por fusiones posibles
    merge_bonus = 0
    for r in range(4):
        for c in range(3):
            if board[r][c] == board[r][c+1] and board[r][c] != 0:
                merge_bonus += board[r][c]
    for c in range(4):
        for r in range(3):
            if board[r][c] == board[r+1][c] and board[r][c] != 0:
                merge_bonus += board[r][c]
    return empty * 500 + max_tile * 100 + corner - penalty + merge_bonus * 20

def get_best_move_that_changes(board, last_move=None):
    """Devuelve el movimiento con mayor puntuación que SÍ modifique el tablero."""
    moves = ["UP", "DOWN", "LEFT", "RIGHT"]
    valid = []
    for m in moves:
        new_board = simulate_move(board, m)
        if new_board != board:
            score = heuristic_score(new_board)
            valid.append((m, score))
    if not valid:
        return None
    valid.sort(key=lambda x: x[1], reverse=True)
    # Evitar repetir el mismo movimiento si hay alternativas decentes
    if last_move and len(valid) > 1 and valid[0][0] == last_move:
        # Con probabilidad 40% usar el segundo mejor
        if random.random() < 0.4:
            return valid[1][0]
    return valid[0][0]

# =========================
# ENVIAR MOVIMIENTO
# =========================
def send_move(driver, move):
    driver.execute_script(f"""
        var event = new KeyboardEvent('keydown', {{
            key: 'Arrow{move.title()}',
            code: 'Arrow{move.title()}',
            bubbles: true
        }});
        document.dispatchEvent(event);
    """)

# =========================
# REINICIAR JUEGO
# =========================
def restart_game(driver):
    try:
        btn = driver.find_element(By.CLASS_NAME, "restart-button")
        btn.click()
        time.sleep(0.8)
        print("🔄 Juego reiniciado")
        return True
    except:
        driver.refresh()
        time.sleep(2)
        return False

# =========================
# BUCLE PRINCIPAL CON DESESTANCAMIENTO FORZADO
# =========================
def main():
    print("📥 Descargando juego...")
    html = get_local_game_html()
    if not html:
        return

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get("data:text/html," + html.replace("#", "%23"))
    time.sleep(2)
    driver.find_element(By.TAG_NAME, "body").click()
    print("✅ Juego listo. Bot iniciado.")

    last_board = None
    last_move = None
    no_change_count = 0
    same_move_count = 0
    move_history = []

    while True:
        try:
            time.sleep(0.1)
            board = get_board_js(driver)

            if not board or all(v == 0 for row in board for v in row):
                time.sleep(0.3)
                continue

            # Game Over
            if driver.find_elements(By.CLASS_NAME, "game-over") and driver.find_element(By.CLASS_NAME, "game-over").is_displayed():
                print("💀 Game Over. Reiniciando...")
                restart_game(driver)
                time.sleep(1)
                last_board = None
                no_change_count = 0
                same_move_count = 0
                move_history.clear()
                continue

            # Si el tablero no cambió después del último movimiento, incrementar contador
            if last_board is not None:
                if board == last_board:
                    no_change_count += 1
                else:
                    no_change_count = 0
            else:
                no_change_count = 0

            # Si estamos estancados (más de 1 movimiento sin cambio), forzar un movimiento aleatorio
            if no_change_count >= 2:
                print(f"⚠️ Estancamiento detectado (no_change_count={no_change_count}). Forzando movimiento aleatorio...")
                move = random.choice(["UP", "DOWN", "LEFT", "RIGHT"])
                send_move(driver, move)
                time.sleep(0.15)
                # Verificar si el tablero cambió después del movimiento forzado
                time.sleep(0.1)
                new_board = get_board_js(driver)
                if new_board == board:
                    # Sigue igual, problema grave: reiniciar juego
                    print("❌ El tablero no cambia incluso con movimiento aleatorio. Reiniciando juego...")
                    restart_game(driver)
                    time.sleep(1)
                    last_board = None
                    no_change_count = 0
                    same_move_count = 0
                    move_history.clear()
                else:
                    last_board = new_board
                    no_change_count = 0
                continue

            # Obtener mejor movimiento que cambie el tablero
            move = get_best_move_that_changes(board, last_move)
            if move is None:
                # No hay movimientos válidos (raro), reiniciar
                print("⚠️ No hay movimientos que cambien el tablero. Reiniciando...")
                restart_game(driver)
                time.sleep(1)
                last_board = None
                no_change_count = 0
                continue

            # Control de movimientos repetidos
            if move == last_move:
                same_move_count += 1
            else:
                same_move_count = 0

            # Si repetimos el mismo movimiento 2 veces seguidas, forzar un cambio
            if same_move_count >= 2:
                print("⚠️ Movimiento repetido. Forzando alternativa...")
                # Buscar otro movimiento que cambie el tablero
                moves = ["UP", "DOWN", "LEFT", "RIGHT"]
                for alternative in moves:
                    if alternative != move:
                        new_board_alt = simulate_move(board, alternative)
                        if new_board_alt != board:
                            move = alternative
                            same_move_count = 0
                            break
                else:
                    # No hay alternativa, reiniciar
                    print("❌ No se encontró alternativa. Reiniciando...")
                    restart_game(driver)
                    time.sleep(1)
                    last_board = None
                    continue

            send_move(driver, move)
            last_move = move
            last_board = [row[:] for row in board]

            # Pequeña pausa
            time.sleep(0.12)

        except Exception as e:
            print(f"⚠️ Error: {e}. Recuperando...")
            try:
                driver.refresh()
                time.sleep(2)
                driver.find_element(By.TAG_NAME, "body").click()
            except:
                driver.quit()
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
                driver.get("data:text/html," + html)
                time.sleep(2)
                driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(1)

if __name__ == "__main__":
    main()