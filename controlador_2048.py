import time
import requests
import copy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# =========================
# JUEGO LOCAL SIN PUBLICIDAD
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
chrome_options.add_argument("--headless")        # Comenta para ver la ventana
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1024,768")

# =========================
# OBTENER TABLERO CON JS
# =========================
def get_board(driver):
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
# ENVIAR TECLA
# =========================
def send_key(driver, direction):
    driver.execute_script(f"""
        var event = new KeyboardEvent('keydown', {{
            key: 'Arrow{direction.title()}',
            code: 'Arrow{direction.title()}',
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
        time.sleep(0.5)
    except:
        driver.refresh()
        time.sleep(2)
    driver.find_element(By.TAG_NAME, "body").click()
    print("🔄 Juego reiniciado")

# ==========================================
# MOTOR DE SIMULACIÓN LÓGICA DE 2048 (INTERNO)
# ==========================================
def merge_line(line):
    """Comprime y fusiona una sola línea (fila o columna) hacia la izquierda"""
    # 1. Quitar ceros
    non_zeros = [v for v in line if v != 0]
    new_line = []
    skip = False
    # 2. Fusionar elementos idénticos contiguos
    for i in range(len(non_zeros)):
        if skip:
            skip = False
            continue
        if i + 1 < len(non_zeros) and non_zeros[i] == non_zeros[i+1]:
            new_line.append(non_zeros[i] * 2)
            skip = True
        else:
            new_line.append(non_zeros[i])
    # 3. Rellenar con ceros restantes
    while len(new_line) < 4:
        new_line.append(0)
    return new_line

def simulate_move(board, direction):
    """Devuelve una copia del tablero tras aplicar un movimiento simulado"""
    sim_board = copy.deepcopy(board)
    
    if direction == "LEFT":
        for i in range(4):
            sim_board[i] = merge_line(sim_board[i])
            
    elif direction == "RIGHT":
        for i in range(4):
            reversed_line = sim_board[i][::-1]
            merged = merge_line(reversed_line)
            sim_board[i] = merged[::-1]
            
    elif direction == "UP":
        for col in range(4):
            line = [sim_board[row][col] for row in range(4)]
            merged = merge_line(line)
            for row in range(4):
                sim_board[row][col] = merged[row]
                
    elif direction == "DOWN":
        for col in range(4):
            line = [sim_board[row][col] for row in range(4)][::-1]
            merged = merge_line(line)
            merged = merged[::-1]
            for row in range(4):
                sim_board[row][col] = merged[row]
                
    return sim_board

# ==========================================
# BUCLE PRINCIPAL INTELIGENTE
# ==========================================
def main():
    html = get_local_game_html()
    if not html:
        return
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get("data:text/html," + html)
    time.sleep(2)
    driver.find_element(By.TAG_NAME, "body").click()
    print("🚀 Bot Inteligente Iniciado. Estrategia: Esquina Inferior Izquierda con Filtro Lógico.")
    
    last_max_tile = 0
    last_progress_time = time.time()
    
    # Prioridad estricta para arrinconar fichas abajo a la izquierda
    strategic_order = ["LEFT", "DOWN", "RIGHT", "UP"]
    
    while True:
        try:
            board = get_board(driver)
            if not board or all(v == 0 for row in board for v in row):
                time.sleep(0.1)
                continue
            
            # 1. Detectar Game Over Oficial
            if driver.find_elements(By.CLASS_NAME, "game-over") and driver.find_element(By.CLASS_NAME, "game-over").is_displayed():
                print("💀 Game Over oficial. Reiniciando...")
                restart_game(driver)
                last_progress_time = time.time()
                last_max_tile = 0
                continue
            
            # 2. Control de progreso (60s de tolerancia)
            current_max = max(max(row) for row in board)
            if current_max > last_max_tile:
                last_max_tile = current_max
                last_progress_time = time.time()
            elif time.time() - last_progress_time > 60:
                print("⏱️ Tablero en bucle cerrado o sin progreso por 60 segundos. Forzando reinicio...")
                restart_game(driver)
                last_max_tile = 0
                last_progress_time = time.time()
                continue
            
            # 3. Filtrar movimientos válidos mediante simulación analítica
            valid_moves = []
            for move in strategic_order:
                simulated = simulate_move(board, move)
                # Si el tablero simulado cambia respecto al actual, significa que el movimiento SÍ es legal
                if simulated != board:
                    valid_moves.append(move)
            
            # 4. Ejecución del mejor movimiento disponible
            if valid_moves:
                # Elegimos el movimiento legal que tenga mayor prioridad en nuestra estrategia de esquina
                best_move = None
                for move in strategic_order:
                    if move in valid_moves:
                        best_move = move
                        break
                
                send_key(driver, best_move)
                # Esperamos un lapso fijo para dejar que la interfaz web procese la aparición de la nueva ficha aleatoria
                time.sleep(0.15)
            else:
                # Si no hay movimientos válidos calculados por el motor, es un Game Over técnico inminente
                print("⚠️ No existen movimientos legales posibles en ningún sentido. Reiniciando...")
                restart_game(driver)
                last_progress_time = time.time()
                last_max_tile = 0
            
            time.sleep(0.02)
            
        except Exception as e:
            print(f"⚠️ Error detectado: {e}. Reiniciando entorno Selenium...")
            try:
                driver.quit()
            except:
                pass
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            driver.get("data:text/html," + html)
            time.sleep(2)
            driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(1)

if __name__ == "__main__":
    main()