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
    """Descarga el HTML del juego desde GitHub (sin recursos externos molestos)."""
    try:
        response = requests.get(GAME_URL, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error descargando el juego: {e}")
        # Fallback: usar un HTML mínimo incrustado (opcional)
        return None

# =========================
# CONFIGURACIÓN DE CHROME PARA AZURE
# =========================
chrome_options = Options()
chrome_options.add_argument("--headless")  # Comenta si quieres ver la ventana
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-web-security")  # Evita CORS en caso de recursos
chrome_options.add_argument("--disable-features=VizDisplayCompositor")
chrome_options.add_argument("--window-size=1024,768")

# =========================
# TABLERO (adaptado al DOM oficial de 2048)
# =========================
def empty_board():
    return [[0]*4 for _ in range(4)]

def parse_tiles(driver):
    """Versión compatible con el HTML original de 2048 (clases 'tile tile-pos-x-y')"""
    tiles = driver.find_elements(By.CSS_SELECTOR, ".tile")
    board = empty_board()
    for tile in tiles:
        try:
            value = int(tile.text)
            # Extraer posición de las clases: tile-position-1-1, etc.
            classes = tile.get_attribute("class")
            # Buscar clase tipo "tile-position-*-*"
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
# HEURÍSTICA Y MOVIMIENTOS (deterministas)
# =========================
def heuristic_score(board):
    empty_cells = sum(row.count(0) for row in board)
    max_tile = max(max(row) for row in board)
    smoothness = 0
    for r in range(4):
        for c in range(3):
            smoothness += abs(board[r][c] - board[r][c+1])
    return empty_cells * 1000 + max_tile * 10 - smoothness

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

def best_move(board):
    moves = ["UP", "DOWN", "LEFT", "RIGHT"]
    best_score = -1
    best_move_chosen = "UP"
    for move in moves:
        new_board = simulate_move(board, move)
        if new_board == board:
            continue
        score = heuristic_score(new_board)
        if score > best_score:
            best_score = score
            best_move_chosen = move
    return best_move_chosen if best_score > -1 else random.choice(moves)

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
# REINICIO AUTOMÁTICO (para la versión local)
# =========================
def restart_game(driver):
    """Hace clic en el botón 'New Game' del juego original."""
    try:
        new_game_btn = driver.find_element(By.CLASS_NAME, "restart-button")
        new_game_btn.click()
        time.sleep(0.5)
        print("🔄 Partida reiniciada")
        return True
    except:
        print("⚠️ No se encontró botón New Game, recargando página...")
        driver.refresh()
        time.sleep(2)
        return False

# =========================
# BUCLE PRINCIPAL (NUNCA SE BLOQUEA)
# =========================
def main():
    # 1. Descargar el juego offline
    print("📥 Descargando juego 2048 sin publicidad...")
    html_content = get_local_game_html()
    if not html_content:
        print("❌ No se pudo obtener el juego. Abortando.")
        return

    # 2. Iniciar driver con opciones seguras para Azure
    print("🚀 Iniciando navegador...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    # 3. Cargar el juego desde una data URI (totalmente local)
    driver.get("data:text/html," + html_content.replace("#", "%23"))  # Escapar #
    time.sleep(2)  # Esperar a que cargue el canvas

    # Asegurar foco en el juego
    driver.find_element(By.TAG_NAME, "body").click()
    print("✅ Juego cargado correctamente. Bot iniciado.")

    while True:
        try:
            board = parse_tiles(driver)
            if not board or all(v == 0 for row in board for v in row):
                time.sleep(0.3)
                continue

            # Detectar Game Over (mensaje en el DOM)
            game_over = driver.find_elements(By.CLASS_NAME, "game-over")
            if game_over and game_over[0].is_displayed():
                print("💀 Game Over detectado. Reiniciando...")
                restart_game(driver)
                time.sleep(1)
                continue

            # Movimiento inteligente
            move = best_move(board)
            send_move(driver, move)
            time.sleep(0.1)  # Pausa para animación

        except Exception as e:
            print(f"⚠️ Error inesperado: {e}")
            # Intento de recuperación: recargar el juego
            try:
                driver.refresh()
                time.sleep(2)
                driver.find_element(By.TAG_NAME, "body").click()
            except:
                print("❌ Error crítico, reiniciando driver...")
                driver.quit()
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
                driver.get("data:text/html," + html_content)
                time.sleep(2)
                driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(1)

if __name__ == "__main__":
    main()