import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))

# =========================
# TABLERO
# =========================
def empty():
    return [[0]*4 for _ in range(4)]

def parse_tiles():
    tiles = driver.find_elements(By.CLASS_NAME, "tile")
    board = empty()

    for t in tiles:
        try:
            value = int(t.text)
            classes = t.get_attribute("class")

            pos = classes.split("tile-position-")
            if len(pos) > 1:
                coords = pos[1].split(" ")[0]
                y, x = map(int, coords.split("-"))

                x -= 1
                y -= 1

                if 0 <= x < 4 and 0 <= y < 4:
                    board[y][x] = max(board[y][x], value)
        except:
            pass

    return board

# =========================
# SCORE MÁS INTELIGENTE
# =========================
def score(board):
    empty = sum(v == 0 for r in board for v in r)
    max_tile = max(max(r) for r in board)

    smooth = 0
    for r in range(4):
        for c in range(3):
            smooth += abs(board[r][c] - board[r][c+1])

    return empty * 1000 + max_tile * 10 - smooth

# =========================
# MOVIMIENTO SIMPLE PERO ESTABLE
# =========================
def random_move(last_move):
    moves = ["UP", "DOWN", "LEFT", "RIGHT"]

    # evita repetir el mismo movimiento
    if last_move in moves:
        moves.remove(last_move)

    return random.choice(moves)

# =========================
# EJECUTAR TECLA
# =========================
def send(move):
    driver.execute_script(f"""
        document.dispatchEvent(new KeyboardEvent('keydown', {{
            key: 'Arrow{move.title()}',
            code: 'Arrow{move.title()}',
            bubbles: true
        }}));
    """)

# =========================
# INICIO
# =========================
driver.get("https://play2048.co/")
time.sleep(3)

driver.find_element(By.TAG_NAME, "body").click()

print("🚀 Bot estable iniciado")

last_move = None
stuck_counter = 0

while True:

    board = parse_tiles()

    if board:
        s = score(board)

        if stuck_counter % 10 == 0:
            print("Score:", s)

        # si está “estancado”, cambia estrategia
        if stuck_counter > 20:
            move = random.choice(["UP", "DOWN", "LEFT", "RIGHT"])
            stuck_counter = 0
        else:
            move = random_move(last_move)

        send(move)

        last_move = move
        stuck_counter += 1

    else:
        send(random.choice(["UP", "LEFT"]))

    time.sleep(0.15)

    if "Game Over" in driver.page_source:
        print("💀 Game Over")
        break

driver.quit()