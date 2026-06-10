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
    return [[0] * 4 for _ in range(4)]

def parse_tiles(driver):
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
    """Puntuación heurística: más vacías, ficha máxima alta, suavidad."""
    empty_cells = sum(row.count(0) for row in board)
    max_tile = max(max(row) for row in board)
    smoothness = 0
    for r in range(4):
        for c in range(3):
            smoothness += abs(board[r][c] - board[r][c+1])
    return empty_cells * 1000 + max_tile * 10 - smoothness

# =========================
# SIMULACIÓN DE MOVIMIENTOS (SIN FICHA ALEATORIA)
# =========================
def compress(row):
    """Mueve los números no cero hacia la izquierda."""
    new_row = [v for v in row if v != 0]
    new_row += [0] * (4 - len(new_row))
    return new_row

def merge(row):
    """Fusiona una fila después de comprimirla."""
    for i in range(3):
        if row[i] == row[i+1] and row[i] != 0:
            row[i] *= 2
            row[i+1] = 0
    return row

def move_row_left(row):
    """Aplica un movimiento a la izquierda en una fila."""
    row = compress(row)
    row = merge(row)
    row = compress(row)
    return row

def move_board_left(board):
    new_board = [move_row_left(row[:]) for row in board]
    return new_board

def move_board_right(board):
    new_board = [move_row_left(row[::-1])[::-1] for row in board]
    return new_board

def transpose(board):
    return [list(row) for row in zip(*board)]

def move_board_up(board):
    transposed = transpose(board)
    moved = move_board_left(transposed)
    return transpose(moved)

def move_board_down(board):
    transposed = transpose(board)
    moved = move_board_right(transposed)
    return transpose(moved)

def simulate_move(board, direction):
    """Devuelve el nuevo tablero después del movimiento (sin ficha nueva)."""
    if direction == "UP":
        return move_board_up(board)
    elif direction == "DOWN":
        return move_board_down(board)
    elif direction == "LEFT":
        return move_board_left(board)
    elif direction == "RIGHT":
        return move_board_right(board)
    else:
        return board

def best_move(board):
    """Elige el movimiento que maximiza la puntuación heurística (determinista)."""
    moves = ["UP", "DOWN", "LEFT", "RIGHT"]
    best_score = -1
    best_move_chosen = "UP"  # default
    for move in moves:
        new_board = simulate_move(board, move)
        # Si el movimiento no cambia el tablero, es peor
        if new_board == board:
            continue
        score = heuristic_score(new_board)
        if score > best_score:
            best_score = score
            best_move_chosen = move
    return best_move_chosen if best_score > -1 else random.choice(moves)

# =========================
# ENVIAR TECLA AL JUEGO
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
# REINICIAR JUEGO AL PERDER
# =========================
def restart_game(driver):
    try:
        # Esperar que el botón "New Game" esté visible y clicable
        new_game_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "restart-button"))
        )
        new_game_btn.click()
        time.sleep(1)
        # En ocasiones el foco se pierde, volvemos a hacer clic en el body
        driver.find_element(By.TAG_NAME, "body").click()
        print("🔄 Juego reiniciado")
    except Exception as e:
        print(f"⚠️ Error al reiniciar: {e}. Recargando página...")
        driver.refresh()
        time.sleep(3)
        driver.find_element(By.TAG_NAME, "body").click()

# =========================
# BUCLE PRINCIPAL (NUNCA SE BLOQUEA)
# =========================
def main():
    # Configurar driver
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    driver.get("https://play2048.co/")
    time.sleep(3)
    driver.find_element(By.TAG_NAME, "body").click()
    print("🚀 Bot inteligente iniciado (sin movimientos aleatorios)")

    while True:
        try:
            # Obtener el tablero actual
            board = parse_tiles(driver)

            if not board:
                # Si no se detectan fichas, esperar y reintentar
                time.sleep(0.5)
                continue

            # Verificar si el juego terminó
            if "Game Over" in driver.page_source:
                print("💀 Game Over detectado. Reiniciando...")
                restart_game(driver)
                # Esperar a que el nuevo tablero cargue
                time.sleep(1)
                continue

            # Elegir el mejor movimiento no aleatorio
            move = best_move(board)
            send_move(driver, move)

            # Pequeña pausa para dar tiempo a la animación
            time.sleep(0.12)

        except Exception as e:
            print(f"⚠️ Error inesperado: {e}. Intentando recuperar...")
            # Si ocurre un error grave, intentamos recargar la página
            try:
                driver.refresh()
                time.sleep(3)
                driver.find_element(By.TAG_NAME, "body").click()
            except:
                print("❌ No se pudo recuperar. Reiniciando driver...")
                driver.quit()
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
                driver.get("https://play2048.co/")
                time.sleep(3)
                driver.find_element(By.TAG_NAME, "body").click()

if __name__ == "__main__":
    main()