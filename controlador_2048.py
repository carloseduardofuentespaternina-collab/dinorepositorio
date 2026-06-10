import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# =========================
# FUNCIONES DEL TABLERO
# =========================
def empty_board():
    return [[0]*4 for _ in range(4)]

def parse_tiles(driver):
    """Lee el tablero actual desde el DOM."""
    tiles = driver.find_elements(By.CLASS_NAME, "tile")
    board = empty_board()
    for t in tiles:
        try:
            value = int(t.text)
            classes = t.get_attribute("class")
            if "tile-position-" in classes:
                pos_part = classes.split("tile-position-")[1].split(" ")[0]
                y, x = map(int, pos_part.split("-"))
                x -= 1
                y -= 1
                if 0 <= x < 4 and 0 <= y < 4:
                    board[y][x] = max(board[y][x], value)
        except:
            pass
    return board

def heuristic_score(board):
    """Puntuación: más vacías mejor, ficha máxima alta, tablero suave."""
    empty_cells = sum(row.count(0) for row in board)
    max_tile = max(max(row) for row in board)
    smoothness = 0
    for r in range(4):
        for c in range(3):
            smoothness += abs(board[r][c] - board[r][c+1])
    return empty_cells * 1000 + max_tile * 10 - smoothness

# =========================
# SIMULACIÓN DE MOVIMIENTOS (SIN ALEATORIEDAD)
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

def best_move(board):
    """Elige el movimiento con mayor puntuación heurística (sin azar)."""
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
    # Si ningún movimiento cambia el tablero (caso raro), devolvemos uno cualquiera
    return best_move_chosen if best_score > -1 else random.choice(moves)

# =========================
# ENVÍO DE TECLAS AL JUEGO
# =========================
def send_move(driver, move):
    driver.execute_script(f"""
        document.dispatchEvent(new KeyboardEvent('keydown', {{
            key: 'Arrow{move.title()}',
            code: 'Arrow{move.title()}',
            bubbles: true
        }}));
    """)

# =========================
# REINICIO ROBUSTO AL PERDER
# =========================
def restart_game(driver):
    """Intenta reiniciar el juego sin cerrar el script."""
    try:
        # Intentar clic en botón "New Game"
        btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "restart-button"))
        )
        btn.click()
        time.sleep(1)
        driver.find_element(By.TAG_NAME, "body").click()
        print("🔄 Partida reiniciada (botón)")
        return True
    except:
        try:
            # Si falla, recargar la página
            driver.refresh()
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "tile"))
            )
            time.sleep(1)
            driver.find_element(By.TAG_NAME, "body").click()
            print("🔄 Partida reiniciada (recarga)")
            return True
        except:
            print("❌ No se pudo reiniciar, se reconstruirá el driver")
            return False

# =========================
# BUCLE PRINCIPAL (NUNCA SE BLOQUEA)
# =========================
def main():
    # Inicializar driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get("https://play2048.co/")
    
    # Esperar a que el juego cargue (máximo 10 segundos)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "tile"))
        )
    except:
        print("⚠️ El juego no cargó a tiempo, recargando...")
        driver.refresh()
        time.sleep(3)
    
    driver.find_element(By.TAG_NAME, "body").click()
    print("🚀 Bot inteligente iniciado (movimientos deterministas)")
    
    while True:
        try:
            # Leer tablero
            board = parse_tiles(driver)
            if not board or all(v == 0 for row in board for v in row):
                # Todavía no hay fichas, esperar un poco
                time.sleep(0.3)
                continue
            
            # Detectar Game Over
            if "Game Over" in driver.page_source:
                print("💀 Game Over detectado")
                if not restart_game(driver):
                    # Si el reinicio falló, reciclamos el driver
                    driver.quit()
                    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
                    driver.get("https://play2048.co/")
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "tile"))
                    )
                    driver.find_element(By.TAG_NAME, "body").click()
                    print("🚀 Driver reiniciado")
                time.sleep(0.5)
                continue
            
            # Elegir mejor movimiento (no aleatorio)
            move = best_move(board)
            send_move(driver, move)
            
            # Pequeña pausa para la animación
            time.sleep(0.1)
            
        except Exception as e:
            print(f"⚠️ Error inesperado: {e}")
            # Intentamos recuperarnos recargando la página
            try:
                driver.refresh()
                time.sleep(3)
                driver.find_element(By.TAG_NAME, "body").click()
                print("🔄 Página recargada por error")
            except:
                print("❌ Error crítico, reiniciando driver...")
                driver.quit()
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
                driver.get("https://play2048.co/")
                time.sleep(3)
                driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(1)

if __name__ == "__main__":
    main()