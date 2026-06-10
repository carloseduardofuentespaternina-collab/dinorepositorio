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
chrome_options.add_argument("--headless")  # Quita esto si quieres ver la ventana
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
# HEURÍSTICA MEJORADA (PESA MUCHO LAS FUSIONES Y LA LIBERTAD)
# =========================
def heuristic_score(board, previous_score=0):
    empty_cells = sum(row.count(0) for row in board)
    max_tile = max(max(row) for row in board)
    
    # Bonificación grande por tener la ficha más alta en la esquina superior izquierda
    corner_bonus = board[0][0] * 3
    
    # Suavidad (diferencias entre vecinos) - se penaliza la rugosidad
    smoothness = 0
    for r in range(4):
        for c in range(3):
            smoothness += abs(board[r][c] - board[r][c+1])
    for c in range(4):
        for r in range(3):
            smoothness += abs(board[r][c] - board[r+1][c])
    
    # Monotonicidad (prefiere filas/columnas ordenadas)
    mono = 0
    for r in range(4):
        for c in range(3):
            if board[r][c] >= board[r][c+1]:
                mono += board[r][c] - board[r][c+1]
            else:
                mono -= board[r][c+1] - board[r][c]
    for c in range(4):
        for r in range(3):
            if board[r][c] >= board[r+1][c]:
                mono += board[r][c] - board[r+1][c]
            else:
                mono -= board[r+1][c] - board[r][c]
    
    # Recompensa por tener fichas iguales adyacentes (para fusionar)
    merge_potential = 0
    for r in range(4):
        for c in range(3):
            if board[r][c] == board[r][c+1] and board[r][c] != 0:
                merge_potential += board[r][c] * 2
    for c in range(4):
        for r in range(3):
            if board[r][c] == board[r+1][c] and board[r][c] != 0:
                merge_potential += board[r][c] * 2
    
    return empty_cells * 1000 + max_tile * 200 + corner_bonus + mono * 10 - smoothness * 2 + merge_potential

# =========================
# SIMULACIÓN DE MOVIMIENTOS (EXACTA)
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

def best_move(board, last_move, consecutive_fails):
    moves = ["UP", "DOWN", "LEFT", "RIGHT"]
    scores = []
    for move in moves:
        new_board = simulate_move(board, move)
        # Si no cambia el tablero, puntuación extremadamente baja
        if new_board == board:
            scores.append((move, -100000))
        else:
            score = heuristic_score(new_board)
            scores.append((move, score))
    
    # Ordenar por puntuación descendente
    scores.sort(key=lambda x: x[1], reverse=True)
    
    # Si estamos teniendo muchos fallos (movimientos sin cambio), forzar el que no sea el último
    if consecutive_fails >= 2:
        # Elegir el primer movimiento que no sea igual al último, si existe
        for move, _ in scores:
            if move != last_move:
                return move
        return scores[0][0]
    
    # Si el mejor movimiento es el mismo que el anterior y hay segundo, 40% de probabilidad de cambiar
    if last_move and scores[0][0] == last_move and len(scores) > 1:
        if random.random() < 0.4:
            return scores[1][0]
    
    return scores[0][0]

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
# BUCLE PRINCIPAL CON CONTROL DE ESTANCAMIENTO
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
    
    last_board = None
    last_move = None
    no_change_counter = 0
    last_max_tile = 0
    moves_without_progress = 0
    last_score = 0
    
    while True:
        try:
            time.sleep(0.08)  # Pequeña pausa para estabilidad
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
                no_change_counter = 0
                moves_without_progress = 0
                continue
            
            # Calcular puntuación actual (heurística simple)
            current_max = max(max(row) for row in board)
            current_empty = sum(row.count(0) for row in board)
            current_score = current_max * 100 + current_empty * 10
            
            # Detectar progreso
            if current_max > last_max_tile:
                moves_without_progress = 0
                last_max_tile = current_max
            else:
                moves_without_progress += 1
            
            # Detectar si el tablero cambió después del movimiento anterior
            if last_board is not None:
                if board == last_board:
                    no_change_counter += 1
                else:
                    no_change_counter = 0
            else:
                no_change_counter = 0
            
            # Si llevamos muchos movimientos sin progreso O sin cambios, forzar movimiento aleatorio
            if moves_without_progress > 12 or no_change_counter >= 2:
                print(f"⚠️ Estancamiento (sin progreso: {moves_without_progress}, sin cambios: {no_change_counter}). Forzando movimiento aleatorio...")
                move = random.choice(["UP", "DOWN", "LEFT", "RIGHT"])
                no_change_counter = 0
                moves_without_progress = 0
            else:
                move = best_move(board, last_move, no_change_counter)
            
            send_move(driver, move)
            last_move = move
            last_board = [row[:] for row in board]
            
            time.sleep(0.1)
            
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