import time
import random
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# =========================
# OBTENER HTML LOCAL (SIN ANUNCIOS)
# =========================
GAME_URL = "https://raw.githubusercontent.com/gabrielecirulli/2048/master/index.html"

def get_local_game_html():
    try:
        response = requests.get(GAME_URL, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error descargando juego: {e}")
        return None

# =========================
# CONFIGURACIÓN CHROME
# =========================
chrome_options = Options()
# chrome_options.add_argument("--headless")  # Descomentar para producción
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1024,768")

# =========================
# OBTENER TABLERO CON JAVASCRIPT
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
# HEURÍSTICA (FAVORECE MOVIMIENTOS QUE ABREN EL TABLERO)
# =========================
def heuristic_score(board):
    empty_cells = sum(row.count(0) for row in board)
    max_tile = max(max(row) for row in board)
    
    # Bonificación fuerte por tener la ficha más grande en esquina
    corner_bonus = board[0][0] * 4
    
    # Penalización por fichas lejos de la esquina
    isolation = 0
    for r in range(4):
        for c in range(4):
            if board[r][c]:
                isolation += board[r][c] * (abs(r) + abs(c))
    
    # Suavidad
    smoothness = 0
    for r in range(4):
        for c in range(3):
            smoothness += abs(board[r][c] - board[r][c+1])
    for c in range(4):
        for r in range(3):
            smoothness += abs(board[r][c] - board[r+1][c])
    
    # Monotonicidad
    mono = 0
    for r in range(4):
        for c in range(3):
            mono += board[r][c] - board[r][c+1] if board[r][c] >= board[r][c+1] else -(board[r][c+1] - board[r][c])
    for c in range(4):
        for r in range(3):
            mono += board[r][c] - board[r+1][c] if board[r][c] >= board[r+1][c] else -(board[r+1][c] - board[r][c])
    
    # Potencial de fusión
    merge_potential = 0
    for r in range(4):
        for c in range(3):
            if board[r][c] == board[r][c+1] and board[r][c]:
                merge_potential += board[r][c] * 2
    for c in range(4):
        for r in range(3):
            if board[r][c] == board[r+1][c] and board[r][c]:
                merge_potential += board[r][c] * 2
    
    return (empty_cells * 800 +
            max_tile * 100 +
            corner_bonus * 50 -
            isolation * 1.5 +
            mono * 8 -
            smoothness * 2 +
            merge_potential * 10)

# =========================
# SIMULACIÓN DE MOVIMIENTOS
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

def get_moves_ordered_by_score(board):
    """Devuelve lista de (movimiento, puntuación) ordenada de mejor a peor, solo movimientos que cambien el tablero."""
    moves = ["UP", "DOWN", "LEFT", "RIGHT"]
    scores = []
    for move in moves:
        new_board = simulate_move(board, move)
        if new_board != board:
            scores.append((move, heuristic_score(new_board)))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores

# =========================
# ENVIAR MOVIMIENTO (JS)
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
        print("🔄 Partida reiniciada")
        return True
    except:
        driver.refresh()
        time.sleep(2)
        return False

# =========================
# ESPERAR A QUE EL TABLERO CAMBIE (CON TIMEOUT)
# =========================
def wait_for_board_change(driver, original_board, timeout=0.5):
    start = time.time()
    while time.time() - start < timeout:
        new_board = get_board_js(driver)
        if new_board != original_board:
            return new_board
        time.sleep(0.05)
    return None  # No cambió

# =========================
# BUCLE PRINCIPAL CON RECUPERACIÓN TOTAL
# =========================
def main():
    print("📥 Descargando juego 2048...")
    html = get_local_game_html()
    if not html:
        return
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get("data:text/html," + html.replace("#", "%23"))
    time.sleep(2)
    driver.find_element(By.TAG_NAME, "body").click()
    print("✅ Juego cargado. Bot iniciado.")
    
    consecutive_no_change = 0
    desperation_mode = False
    desperation_counter = 0
    last_score_heuristic = 0
    
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
                consecutive_no_change = 0
                desperation_mode = False
                continue
            
            # Modo desesperación: si llevamos muchos fallos, forzar movimientos aleatorios
            if desperation_mode:
                moves = ["UP", "DOWN", "LEFT", "RIGHT"]
                move = random.choice(moves)
                print(f"🔥 Modo desesperación: movimiento aleatorio {move}")
                send_move(driver, move)
                time.sleep(0.15)
                new_board = wait_for_board_change(driver, board, timeout=0.5)
                if new_board is not None:
                    desperation_counter += 1
                    if desperation_counter >= 5:
                        desperation_mode = False
                        desperation_counter = 0
                        print("✅ Saliendo de modo desesperación")
                else:
                    # Tampoco cambió con aleatorio, reiniciamos
                    print("⚠️ Sin cambios incluso en modo desesperación, reiniciando...")
                    restart_game(driver)
                    desperation_mode = False
                    continue
                continue
            
            # Obtener movimientos ordenados (solo los que cambian el tablero)
            valid_moves = get_moves_ordered_by_score(board)
            if not valid_moves:
                print("⚠️ No hay movimientos válidos. Reiniciando juego...")
                restart_game(driver)
                time.sleep(1)
                continue
            
            # Intentar cada movimiento en orden hasta que uno realmente cambie el tablero
            move_executed = False
            for move, _ in valid_moves:
                send_move(driver, move)
                time.sleep(0.15)
                new_board = wait_for_board_change(driver, board, timeout=0.5)
                if new_board is not None:
                    move_executed = True
                    break
                else:
                    print(f"⚠️ Movimiento {move} no cambió el tablero, probando siguiente...")
            
            if not move_executed:
                # Ningún movimiento produjo cambio → juego roto o bloqueado
                print("❌ Todos los movimientos no cambiaron el tablero. Reiniciando...")
                restart_game(driver)
                time.sleep(1)
                consecutive_no_change = 0
                continue
            
            # Evaluar progreso
            new_board = get_board_js(driver)
            current_heuristic = heuristic_score(new_board)
            if current_heuristic <= last_score_heuristic + 100:  # No mejora significativamente
                consecutive_no_change += 1
            else:
                consecutive_no_change = 0
            
            last_score_heuristic = current_heuristic
            
            # Si llevamos 8 movimientos sin mejora, activar modo desesperación
            if consecutive_no_change >= 8:
                print("⚠️ Estancamiento detectado, activando modo desesperación")
                desperation_mode = True
                desperation_counter = 0
                consecutive_no_change = 0
            
        except Exception as e:
            print(f"⚠️ Error inesperado: {e}. Recuperando...")
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