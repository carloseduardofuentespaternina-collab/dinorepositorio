import time
import copy
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
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
# LEER TABLERO CON PROTECCIÓN
# ──────────────────────────────────────────

def leer_tablero(driver):
    tablero = [[0]*4 for _ in range(4)]
    try:
        tiles = driver.find_elements(By.CSS_SELECTOR, ".tile")
        for tile in tiles:
            try:
                classes = tile.get_attribute("class").split()
                pos = [c for c in classes if c.startswith("tile-position-")]
                val = [
                    c for c in classes
                    if c.startswith("tile-")
                    and not c.startswith("tile-position")
                    and not c.startswith("tile-merged")
                    and not c.startswith("tile-new")
                    and not c.startswith("tile-super")
                ]
                if pos and val:
                    partes = pos[0].split("-")
                    col = int(partes[2]) - 1
                    row = int(partes[3]) - 1
                    valor = int(val[0].replace("tile-", ""))
                    # Quedarse con el mayor valor si hay duplicado (tile animado)
                    if 0 <= row < 4 and 0 <= col < 4:
                        tablero[row][col] = max(tablero[row][col], valor)
            except (ValueError, IndexError, StaleElementReferenceException):
                continue  # tile en animación, ignorar
    except WebDriverException:
        pass
    return tablero

def tablero_valido(tablero):
    """Verifica que el tablero no esté completamente vacío."""
    return any(tablero[r][c] != 0 for r in range(4) for c in range(4))

# ──────────────────────────────────────────
# LÓGICA DEL TABLERO
# ──────────────────────────────────────────

def mover_fila_izq(fila):
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
    return nuevo, (nuevo != tablero)

# ──────────────────────────────────────────
# HEURÍSTICAS
# ──────────────────────────────────────────

PESO_ESQUINA = [
    [16,  8,  4,  2],
    [ 8,  4,  2,  1],
    [ 4,  2,  1,  0.5],
    [ 2,  1, 0.5, 0.25],
]

def evaluar(tablero):
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
            score += v * PESO_ESQUINA[r][c]
            if c + 1 < 4 and tablero[r][c+1]:
                suavidad -= abs(v - tablero[r][c+1])
            if r + 1 < 4 and tablero[r+1][c]:
                suavidad -= abs(v - tablero[r+1][c])
    for r in range(4):
        fila = [tablero[r][c] for c in range(4) if tablero[r][c]]
        if fila == sorted(fila, reverse=True) or fila == sorted(fila):
            monotonia += sum(fila)
    for c in range(4):
        col = [tablero[r][c] for r in range(4) if tablero[r][c]]
        if col == sorted(col, reverse=True) or col == sorted(col):
            monotonia += sum(col)
    return score + vacias * 50 + monotonia * 2 + suavidad * 0.5

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
                mejor = max(mejor, expectimax(nuevo, profundidad - 1, False))
        return mejor if alguno else evaluar(tablero)
    else:
        vacias = [(r, c) for r in range(4) for c in range(4) if tablero[r][c] == 0]
        if not vacias:
            return expectimax(tablero, profundidad, True)
        total = 0
        # ✅ Limitar celdas evaluadas para no explotar el tiempo
        muestra = vacias[:4] if len(vacias) > 4 else vacias
        for r, c in muestra:
            for val, prob in [(2, 0.9), (4, 0.1)]:
                copia = copy.deepcopy(tablero)
                copia[r][c] = val
                total += prob * expectimax(copia, profundidad - 1, True)
        return total / len(muestra)

def mejor_movimiento(tablero):
    vacias = sum(1 for r in range(4) for c in range(4) if tablero[r][c] == 0)
    # ✅ Profundidad máxima 3 para evitar timeouts
    profundidad = 3 if vacias >= 4 else 2

    mejor_dir = None
    mejor_val = -float("inf")
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
# OBTENER body CON REINTENTO
# ──────────────────────────────────────────

def get_body():
    """Obtiene body fresco para evitar StaleElementReference."""
    for _ in range(3):
        try:
            return driver.find_element(By.TAG_NAME, "body")
        except WebDriverException:
            time.sleep(0.5)
    return None

# ──────────────────────────────────────────
# BUCLE PRINCIPAL
# ──────────────────────────────────────────

try:
    print("Conectando al juego 2048...")
    driver.get("https://play2048.co/")
    time.sleep(3)
    print("Juego iniciado — Expectimax protegido\n")

    tablero_anterior = None
    movimientos_sin_cambio = 0

    for i in range(2000):

        # ✅ Leer tablero y validar
        tablero = leer_tablero(driver)

        if not tablero_valido(tablero):
            print("Tablero vacío, esperando DOM...")
            time.sleep(0.3)
            continue

        # ✅ Detectar si el tablero no cambió (posible bloqueo)
        if tablero == tablero_anterior:
            movimientos_sin_cambio += 1
            if movimientos_sin_cambio >= 20:
                print("Tablero sin cambios, posible bloqueo. Saliendo.")
                break
        else:
            movimientos_sin_cambio = 0
        tablero_anterior = tablero

        maximo = max(tablero[r][c] for r in range(4) for c in range(4))

        # ✅ Calcular mejor movimiento
        direccion = mejor_movimiento(tablero)

        if direccion is None:
            print("Sin movimientos válidos detectados.")
            break

        # ✅ Obtener body fresco en cada iteración
        body = get_body()
        if body is None:
            print("No se pudo obtener body, reintentando...")
            time.sleep(1)
            continue

        try:
            body.send_keys(KEY_MAP[direccion])
        except StaleElementReferenceException:
            print("Body stale, reintentando...")
            time.sleep(0.3)
            continue
        except WebDriverException as e:
            print(f"Error enviando tecla: {e}")
            break

        if i % 20 == 0:
            print(f"Mov {i:4d} | Tile máx: {maximo:4d} | Dir: {direccion} | Vacías: {sum(1 for r in range(4) for c in range(4) if tablero[r][c]==0)}")

        time.sleep(0.1)

        # ✅ Detectar estados de fin
        try:
            if driver.find_elements(By.CLASS_NAME, "game-over"):
                maximo = max(leer_tablero(driver)[r][c] for r in range(4) for c in range(4))
                print(f"\n💀 Game Over — Tile máximo: {maximo}")
                break
            if driver.find_elements(By.CLASS_NAME, "game-won"):
                print("\n🎉 ¡Ganaste! Llegaste a 2048")
                break
        except WebDriverException:
            pass

    print("\nPrueba finalizada")

except Exception as e:
    print(f"Error inesperado: {e}")
    raise

finally:
    time.sleep(5)
    driver.quit()