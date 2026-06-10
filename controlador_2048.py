import time
import random
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# =========================
# OBTENER HTML DEL JUEGO (SIN PUBLICIDAD)
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
# CONFIGURACIÓN CHROME (PARA AZURE)
# =========================
chrome_options = Options()
chrome_options.add_argument("--headless")  # Comentar si quieres ver ventana
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-web-security")
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
# HEURÍSTICA MEJORADA
# =========================
def heuristic_score(board):
    empty_cells = sum(row.count(0) for row in board)
    max_tile = max(max(row) for row in board)
    corner_bonus = board[0][0] * 2
    smoothness = 0
    for r in range(4):
        for c in range(3):
            smoothness += abs(board[r][c] - board[r][c+1])
    for c in range(4):
        for r in range(3):
            smoothness += abs(board[r][c] - board[r+1][c])
    monotonicity = 0
    for r in range(4):
        for c in range(3):
            if board[r][c] >= board[r][c+1]:
                monotonicity += board[r][c] - board[r][c+1]
            else:
                monotonicity -= board[r][c+1] - board[r][c]
    for c in range(4):
        for r in range(3):
            if board[r][c] >= board[r+1][c]:
                monotonicity += board[r][c] - board[r+1][c]
            else:
                monotonicity -= board[r+1][c] - board[r][c]
    return empty_cells * 800 + max_tile * 50 + corner_bonus + monotonicity - smoothness

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
    row = compress(row)
    row = merge(row)
    row = compress(row)
    return row

def move_board_left(board):
    return [move_row_left(row[:]) for row in board]

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

def best_move(board, last_move, stuck_counter, mode_explore=False):
    moves = ["UP", "DOWN", "LEFT", "RIGHT"]
    scores = []
    for move in moves:
        new_board = simulate_move(board, move)
        if new_board == board:
            scores.append((move, -10000))
        else:
            score = heuristic_score(new_board)
            scores.append((move, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    
    # Modo exploración: elegir aleatorio entre los dos mejores (para romper loops)
    if mode_explore:
        best_two = scores[:2]
        return random.choice([best_two[0][0], best_two[1][0]] if len(best_two) > 1 else [scores[0][0]])
    
    # Si estamos muy estancados, elegir un movimiento diferente al último
    if stuck_counter > 4 and len(scores) > 1:
        if scores[0][0] == last_move:
            return scores[1][0]
    
    # Si el mejor es el mismo que el anterior, a veces cambiar
    if last_move and scores[0][0] == last_move and len(scores) > 1:
        if random.random() < 0.4:
            return scores[1][0]
    return scores[0][0]

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
        print("🔄 Reiniciado")
        return True
    except:
        driver.refresh()
        time.sleep(2)
        return False

# =========================
# BUCLE PRINCIPAL CON ESTANCAMIENTO MEJORADO
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
    stuck_counter = 0
    no_change_counter = 0
    last_max_tile = 0
    mode_explore = False
    explore_until = 0  # Timestamp hasta cuando explorar
    
    while True:
        try:
            time.sleep(0.08)  # Espera breve
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
                stuck_counter = 0
                mode_explore = False
                continue
            
            # Calcular ficha máxima actual
            current_max = max(max(row) for row in board)
            if current_max > last_max_tile:
                last_max_tile = current_max
                stuck_counter = 0
                no_change_counter = 0
                mode_explore = False
            else:
                # Si no ha mejorado la ficha máxima en varios ciclos, incrementar contador
                if last_board is not None:
                    if board == last_board:
                        no_change_counter += 1
                    else:
                        no_change_counter = 0
                # Estancamiento: si llevamos 8 movimientos sin mejorar ficha máxima
                if stuck_counter > 8:
                    print("⚠️ Estancamiento grave, activando modo exploración...")
                    mode_explore = True
                    explore_until = time.time() + 5  # 5 segundos de exploración
                elif stuck_counter > 5 and not mode_explore:
                    print("⚠️ Estancamiento moderado, aumentando aleatoriedad...")
            
            # Si estamos en modo exploración, verificar si ya pasó el tiempo
            if mode_explore and time.time() > explore_until:
                mode_explore = False
                print("✅ Volviendo a modo normal")
            
            # Forzar aleatorio si no hay cambios después de 2 movimientos
            if no_change_counter >= 2:
                print("⚠️ Sin cambios, forzando movimiento aleatorio")
                move = random.choice(["UP", "DOWN", "LEFT", "RIGHT"])
                no_change_counter = 0
                stuck_counter += 1
            else:
                move = best_move(board, last_move, stuck_counter, mode_explore)
            
            send_move(driver, move)
            last_move = move
            last_board = [row[:] for row in board]
            stuck_counter += 1
            
            time.sleep(0.1)
            
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