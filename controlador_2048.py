import time
import copy
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)

# ──────────────────────────────────────────
# LÓGICA DEL TABLERO (simulación interna)
# ──────────────────────────────────────────

def leer_tablero(driver):
    """Lee el tablero desde el DOM."""
    tablero = [[0]*4 for _ in range(4)]
    try:
        tiles = driver.find_elements(By.CSS_SELECTOR, ".tile")
        for tile in tiles:
            classes = tile.get_attribute("class").split()
            pos = [c for c in classes if c.startswith("tile-position-")]
            val = [c for c in classes if c.startswith("tile-") and not c.startswith("tile-position") and not c.startswith("tile-merged") and not c.startswith("tile-new") and not c.startswith("tile-super")]
            if pos and val:
                try:
                    partes = pos[0].split("-")
                    col = int(partes[2]) - 1  # 1-indexed → 0-indexed
                    row = int(partes[3]) - 1
                    valor = int(val[0].replace("tile-", ""))
                    tablero[row][col] = valor
                except Exception:
                    pass
    except Exception:
        pass
    return tablero

def mover_fila_izq(fila):
    """Mueve y combina una fila hacia la izquierda."""
    fila = [x for x in fila if x != 0]
    nueva = []
    i = 0
    while i < len(fila):
        if i + 1 < len(fila) and fila[i] == fila[i+1]:
            nueva.append(fila[i] * 2)
            i += 2
        else:
            nueva.append(fila[i])
            i += 1
    return nueva + [0] * (4 - len(nueva))

def simular_movimiento(tablero, direccion):
    """Simula un movimiento y retorna (nuevo_tablero, cambió)."""
    t = copy.deepcopy(tablero)

    if direccion == "izq":
        nuevo = [mover_fila_izq(fila) for fila in t]
    elif direccion == "der":
        nuevo = [mover_fila_izq(fila[::-1])[::-1] for fila in t]
    elif direccion == "arr":
        cols = [[t[r][c] for r in range(4)] for c in range(4)]
        cols = [mover_fila_izq(col) for col in cols]
        nuevo = [[cols[c][r] for c in range(4)] for r in range(4)]
    elif direccion == "aba":
        cols = [[t[r][c] for r in range(4)] for c in range(4)]
        cols = [mover_fila_izq(col[::-1])[::-1] for col in cols]
        nuevo = [[cols[c][r] for c in range(4)] for r in range(4)]

    cambio = (nuevo != tablero)
    return nuevo, cambio

# ──────────────────────────────────────────
# HEURÍSTICAS DE EVALUACIÓN
# ──────────────────────────────────────────

PESO_ESQUINA = [
    [16,  8,  4,  2],
    [ 8,  4,  2,  1],
    [ 4,  2,  1,  0.5],
    [ 2,  1, 0.5, 0.25],
]

def evaluar(tablero):
    """Puntúa el tablero con múltiples heurísticas."""
    score = 0
    vacias = 0
    monotonia = 0
    suavidad = 0

    for r in range(4):
        for c in range(4):
            v = tablero[r][c]
            if v == 0:
                vacias += 1
                continue

            # Peso por posición (esquina superior-izquierda = mejor)
            score += v * PESO_ESQUINA[r][c]

            # Suavidad: penaliza diferencias grandes entre vecinos
            if c + 1 < 4 and tablero[r][c+1]:
                suavidad -= abs(v - tablero[r][c+1])
            if r + 1 < 4 and tablero[r+1][c]:
                suavidad -= abs(v - tablero[r+1][c])

    # Monotonía horizontal y vertical
    for r in range(4):
        fila = [tablero[r][c] for c in range(4) if tablero[r][c]]
        if fila == sorted(fila, reverse=True) or fila == sorted(fila):
            monotonia += sum(fila)

    for c in range(4):
        col = [tablero[r][c] for r in range(4) if tablero[r][c]]
        if col == sorted(col, reverse=True) or col == sorted(col):
            monotonia += sum(col)

    return score + vacias * 50 + monotonia * 2 + suavidad * 0.5

# ──────────────────────────────────────────
# EXPECTIMAX (profundidad 3)
# ──────────────────────────────────────────

DIRS = ["arr", "izq", "aba", "der"]

def expectimax(tablero, profundidad, es_jugador):
    if profundidad == 0:
        return evaluar(tablero)

    if es_jugador:
        mejor = -float("inf")
        alguno = False
        for d in DIRS:
            nuevo, cambio = simular_movimiento(tablero, d)
            if cambio:
                alguno = True
                val = expectimax(nuevo, profundidad - 1, False)
                mejor = max(mejor, val)
        return mejor if alguno else evaluar(tablero)
    else:
        # Nodo azar: promedia colocar 2 o 4 en cada celda vacía
        vacias = [(r, c) for r in range(4) for c in range(4) if tablero[r][c] == 0]
        if not vacias:
            return expectimax(tablero, profundidad, True)
        total = 0
        for r, c in vacias:
            for val, prob in [(2, 0.9), (4, 0.1)]:
                copia = copy.deepcopy(tablero)
                copia[r][c] = val
                total += prob * expectimax(copia, profundidad - 1, True)
        return total / len(vacias)

def mejor_movimiento(tablero):
    """Elige el mejor movimiento según Expectimax."""
    mejor_dir = None
    mejor_val = -float("inf")

    # Limitar profundidad según celdas vacías (más vacías = más rápido)
    vacias = sum(1 for r in range(4) for c in range(4) if tablero[r][c] == 0)
    profundidad = 4 if vacias >= 6 else 3 if vacias >= 3 else 2

    for d in DIRS:
        nuevo, cambio = simular_movimiento(tablero, d)
        if cambio:
            val = expectimax(nuevo, profundidad, False)
            if val > mejor_val:
                mejor_val = val
                mejor_dir = d

    return mejor_dir

KEY_MAP = {
    "arr": Keys.UP,
    "izq": Keys.LEFT,
    "aba": Keys.DOWN,
    "der": Keys.RIGHT,
}

# ──────────────────────────────────────────
# BUCLE PRINCIPAL
# ──────────────────────────────────────────

try:
    print("Conectando al juego 2048...")
    driver.get("https://play2048.co/")
    time.sleep(3)

    body = driver.find_element(By.TAG_NAME, "body")
    print("Juego iniciado — usando Expectimax\n")

    for i in range(2000):
        tablero = leer_tablero(driver)
        maximo = max(tablero[r][c] for r in range(4) for c in range(4))

        direccion = mejor_movimiento(tablero)

        if direccion is None:
            print("Sin movimientos válidos.")
            break

        body.send_keys(KEY_MAP[direccion])

        if i % 20 == 0:
            print(f"Mov {i:4d} | Tile máx: {maximo:4d} | Dir: {direccion}")

        time.sleep(0.08)

        game_over = driver.find_elements(By.CLASS_NAME, "game-over")
        if game_over:
            tablero = leer_tablero(driver)
            maximo = max(tablero[r][c] for r in range(4) for c in range(4))
            print(f"\n💀 Game Over — Tile máximo alcanzado: {maximo}")
            break

        game_won = driver.find_elements(By.CLASS_NAME, "game-won")
        if game_won:
            print("\n🎉 ¡Ganaste! Llegaste a 2048")
            break

    print("\nPrueba finalizada")

except Exception as e:
    print(f"Error: {e}")
    raise

finally:
    time.sleep(5)
    driver.quit()