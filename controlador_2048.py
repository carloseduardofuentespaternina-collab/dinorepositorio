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
chrome_options.add_argument("--headless")  # Quitar para depurar
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
# HEURÍSTICA AVANZADA
# =========================
def heuristic_score(board):
    empty_cells = sum(row.count(0) for row in board)
    max_tile = max(max(row) for row in board)
    
    # Bonificación fuerte por tener la ficha más grande en la esquina superior izquierda
    corner_bonus = board[0][0] * 5
    
    # Penalización por fichas aisladas lejos de la esquina
    isolation_penalty = 0
    for r in range(4):
        for c in range(4):
            if board[r][c] > 0:
                distance = abs(r - 0) + abs(c - 0)  # distancia a la esquina
                isolation_penalty += board[r][c] * distance
    
    # Suavidad (diferencias entre vecinos)
    smoothness = 0
    for r in range(4):
        for c in range(3):
            smoothness += abs(board[r][c] - board[r][c+1])
    for c in range(4):
        for r in range(3):
            smoothness += abs(board[r][c] - board[r+1][c])
    
    # Monotonicidad (valores ordenados)
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
    
    # Potencial de fusión (pares iguales adyacentes)
    merge_potential = 0
    for r in range(4):
        for c in range(3):
            if board[r][c] == board[r][c+1] and board[r][c] != 0:
                merge_potential += board[r][c] * 3
    for c in range(4):
        for r in range(3):
            if board[r][c] == board[r+1][c] and board[r][c] != 0:
                merge_potential += board[r][c] * 3
    
    return (empty_cells * 600 +
            max_tile * 100 +
            corner_bonus * 50 -
            isolation_penalty * 2 +
            mono * 5 -
            smoothness +
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

def best_move_with_change(board, last_board_history):
    """
    Devuelve el mejor movimiento que SÍ cambie el tablero.
    Si ningún movimiento cambia el tablero, retorna None.
    """
    moves = ["UP", "DOWN", "LEFT", "RIGHT"]
    valid_moves = []
    for move in moves:
        new_board = simulate_move(board, move)
        if new_board != board:
            valid_moves.append((move, heuristic_score(new_board)))
    
    if not valid_moves:
        return None
    
    # Ordenar por puntuación
    valid_moves.sort(key=lambda x: x[1], reverse=True)
    
    # Evitar ciclos: si el mejor movimiento lleva a un tablero que ya vimos recientemente, elegir el siguiente
    for move, _ in valid_moves:
        new_board = simulate_move(board, move)
        if new_board not in last_board_history[-5:]:  # últimos 5 tableros
            return move
    # Si todos llevan a ciclos, devolver el mejor de todas formas
    return valid_moves[0][0]

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
        print("🔄 Partida reiniciada")
        return True
    except:
        driver.refresh()
        time.sleep(2)
        return False

# =========================
# BUCLE PRINCIPAL CON CONTROL TOTAL
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
    
    board_history = []  # Guardar tableros recientes
    last_move = None
    stuck_counter = 0
    
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
                board_history.clear()
                stuck_counter = 0
                continue
            
            # Guardar tablero actual en historial
            board_history.append([row[:] for row in board])
            if len(board_history) > 10:
                board_history.pop(0)
            
            # Buscar un movimiento que cambie el tablero
            move = best_move_with_change(board, board_history)
            
            if move is None:
                # No hay movimientos que cambien el tablero → situación imposible de resolver
                print("⚠️ No hay movimientos válidos. Reiniciando juego...")
                restart_game(driver)
                time.sleep(1)
                board_history.clear()
                stuck_counter = 0
                continue
            
            # Enviar movimiento
            send_move(driver, move)
            last_move = move
            
            # Pequeña pausa para que el tablero se actualice
            time.sleep(0.12)
            
            # Verificar si el tablero cambió realmente después del movimiento (por si el JS falla)
            time.sleep(0.05)
            new_board = get_board_js(driver)
            if new_board == board:
                stuck_counter += 1
                if stuck_counter >= 3:
                    print("⚠️ El tablero no cambia después de 3 movimientos. Forzando reinicio...")
                    restart_game(driver)
                    board_history.clear()
                    stuck_counter = 0
                    time.sleep(1)
            else:
                stuck_counter = 0
            
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