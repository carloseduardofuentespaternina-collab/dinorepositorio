import time
import random
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# =========================
# DESCARGAR JUEGO LOCAL (SIN ANUNCIOS)
# =========================
GAME_URL = "https://raw.githubusercontent.com/gabrielecirulli/2048/master/index.html"

def get_local_game_html():
    try:
        response = requests.get(GAME_URL, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error descargando: {e}")
        return None

# =========================
# CONFIGURACIÓN CHROME
# =========================
chrome_options = Options()
chrome_options.add_argument("--headless")  # Quitar si quieres ver la ventana
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-web-security")
chrome_options.add_argument("--window-size=1024,768")

# =========================
# TABLERO
# =========================
def empty_board():
    return [[0]*4 for _ in range(4)]

def parse_tiles(driver):
    tiles = driver.find_elements(By.CSS_SELECTOR, ".tile")
    board = empty_board()
    for tile in tiles:
        try:
            value = int(tile.text)
            classes = tile.get_attribute("class")
            import re
            match = re.search(r"tile-position-(\d+)-(\d+)", classes)
            if match:
                y, x = int(match.group(1)) - 1, int(match.group(2)) - 1
                if 0 <= x < 4 and 0 <= y < 4:
                    board[y][x] = max(board[y][x], value)
        except:
            pass
    return board

# =========================
# HEURÍSTICA AVANZADA
# =========================
def heuristic_score(board):
    empty_cells = sum(row.count(0) for row in board)
    max_tile = max(max(row) for row in board)
    
    # Suavidad (suma de diferencias entre vecinos)
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
    
    # Peso por esquina (favorecer ficha grande en esquina superior izquierda)
    corner_bonus = board[0][0] * 2
    
    return empty_cells * 800 + max_tile * 50 + corner_bonus + mono - smoothness

# =========================
# MOVIMIENTOS (SIMULACIÓN)
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

def best_move(board, previous_move=None):
    moves = ["UP", "DOWN", "LEFT", "RIGHT"]
    best_score = -1
    best_move_chosen = None
    scores = []
    for move in moves:
        new_board = simulate_move(board, move)
        # Si no cambia el tablero, puntuación muy baja
        if new_board == board:
            scores.append((move, -10000))
        else:
            score = heuristic_score(new_board)
            scores.append((move, score))
    # Ordenar por puntuación
    scores.sort(key=lambda x: x[1], reverse=True)
    # Si el mejor movimiento es el mismo que el anterior y hay alternativa, a veces cambiar
    if previous_move and scores[0][0] == previous_move and len(scores) > 1:
        # 30% de probabilidad de tomar el segundo mejor
        if random.random() < 0.3:
            return scores[1][0]
    return scores[0][0]

# =========================
# ENVIAR TECLA
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
# REINICIAR
# =========================
def restart_game(driver):
    try:
        btn = driver.find_element(By.CLASS_NAME, "restart-button")
        btn.click()
        time.sleep(0.5)
        print("🔄 Reiniciado")
        return True
    except:
        driver.refresh()
        time.sleep(2)
        return False

# =========================
# BUCLE PRINCIPAL CON ANTI-ESTANCADO
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
    print("✅ Juego cargado. Bot iniciado.")
    
    last_board = None
    last_move = None
    stuck_counter = 0
    
    while True:
        try:
            board = parse_tiles(driver)
            if not board or all(v == 0 for row in board for v in row):
                time.sleep(0.3)
                continue
            
            # Verificar Game Over
            if driver.find_elements(By.CLASS_NAME, "game-over") and driver.find_element(By.CLASS_NAME, "game-over").is_displayed():
                print("💀 Game Over. Reiniciando...")
                restart_game(driver)
                time.sleep(1)
                last_board = None
                stuck_counter = 0
                continue
            
            # Detectar estancamiento (tablero sin cambios después de varios movimientos)
            if last_board is not None and board == last_board:
                stuck_counter += 1
            else:
                stuck_counter = 0
            
            # Si está estancado, forzar un movimiento diferente (incluso si empeora)
            if stuck_counter > 5:
                print("⚠️ Estancado, forzando movimiento aleatorio...")
                move = random.choice(["UP", "DOWN", "LEFT", "RIGHT"])
                stuck_counter = 0
            else:
                move = best_move(board, last_move)
            
            send_move(driver, move)
            last_move = move
            last_board = [row[:] for row in board]  # Copia profunda
            
            time.sleep(0.12)  # Ligeramente más rápido
            
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