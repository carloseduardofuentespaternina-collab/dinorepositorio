import time
import requests
import copy
import random
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
# MOTOR DE SIMULACIÓN LÓGICA DE 2048
# ==========================================
def merge_line(line):
    non_zeros = [v for v in line if v != 0]
    new_line = []
    skip = False
    for i in range(len(non_zeros)):
        if skip:
            skip = False
            continue
        if i + 1 < len(non_zeros) and non_zeros[i] == non_zeros[i+1]:
            new_line.append(non_zeros[i] * 2)
            skip = True
        else:
            new_line.append(non_zeros[i])
    while len(new_line) < 4:
        new_line.append(0)
    return new_line

def simulate_move(board, direction):
    sim_board = copy.deepcopy(board)
    if direction == "LEFT":
        for i in range(4): sim_board[i] = merge_line(sim_board[i])
    elif direction == "RIGHT":
        for i in range(4): sim_board[i] = merge_line(sim_board[i][::-1])[::-1]
    elif direction == "UP":
        for col in range(4):
            line = merge_line([sim_board[row][col] for row in range(4)])
            for row in range(4): sim_board[row][col] = line[row]
    elif direction == "DOWN":
        for col in range(4):
            line = merge_line([sim_board[row][col] for row in range(4)][::-1])[::-1]
            for row in range(4): sim_board[row][col] = line[row]
    return sim_board

# ==========================================
# DETECTOR DINÁMICO DE MEJOR ESQUINA
# ==========================================
def get_dynamic_moves_order(board):
    """Encuentra la ficha más grande y adapta el orden de movimientos a esa esquina"""
    max_val = -1
    best_row, best_col = 0, 0
    
    for r in range(4):
        for c in range(4):
            if board[r][c] > max_val:
                max_val = board[r][c]
                best_row, best_col = r, c
                
    # Determinar qué esquina es según la posición de la ficha más grande
    if best_row >= 2 and best_col < 2:   # Abajo Izquierda
        return ["LEFT", "DOWN", "RIGHT", "UP"]
    elif best_row >= 2 and best_col >= 2: # Abajo Derecha
        return ["RIGHT", "DOWN", "LEFT", "UP"]
    elif best_row < 2 and best_col >= 2:  # Arriba Derecha (Tu caso actual de las capturas)
        return ["RIGHT", "UP", "LEFT", "DOWN"]
    else:                                 # Arriba Izquierda
        return ["LEFT", "UP", "RIGHT", "DOWN"]

# ==========================================
# BUCLE PRINCIPAL PERFECCIONADO
# ==========================================
def main():
    html = get_local_game_html()
    if not html:
        return
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get("data:text/html," + html)
    time.sleep(2)
    driver.find_element(By.TAG_NAME, "body").click()
    print("🚀 Bot Adaptativo de Alto Rendimiento Iniciado.")
    
    last_max_tile = 0
    last_progress_time = time.time()
    
    # Sistema inteligente anti-vaivén basado en conteo de acciones
    recent_moves = []
    
    while True:
        try:
            board = get_board(driver)
            if not board or all(v == 0 for row in board for v in row):
                time.sleep(0.1)
                continue
            
            # 1. Game Over Real
            if driver.find_elements(By.CLASS_NAME, "game-over") and driver.find_element(By.CLASS_NAME, "game-over").is_displayed():
                print("💀 Game Over detectado de verdad. Reiniciando...")
                restart_game(driver)
                last_progress_time = time.time()
                last_max_tile = 0
                recent_moves.clear()
                continue
            
            # 2. Control de Bloqueo por tiempo prolongado (60s de seguridad)
            current_max = max(max(row) for row in board)
            if current_max > last_max_tile:
                last_max_tile = current_max
                last_progress_time = time.time()
            elif time.time() - last_progress_time > 60:
                print("⏱️ Sin avance en la ficha máxima por 60 segundos. Reiniciando...")
                restart_game(driver)
                last_max_tile = 0
                last_progress_time = time.time()
                recent_moves.clear()
                continue
            
            # 3. Adaptar la estrategia a donde estén tus fichas valiosas reales
            strategic_order = get_dynamic_moves_order(board)
            
            # 4. Calcular qué movimientos modifican matemáticamente el tablero
            valid_moves = [move for move in strategic_order if simulate_move(board, move) != board]
            
            if not valid_moves:
                print("⚠️ Atrapado sin salidas legales. Forzando reinicio...")
                restart_game(driver)
                last_progress_time = time.time()
                last_max_tile = 0
                recent_moves.clear()
                continue
            
            # 5. DETECTOR INTEGRAL DE PING-PONG / VAIVÉN
            # Si el bot lleva más de 4 movimientos alternando de un lado a otro de forma repetitiva...
            if len(recent_moves) >= 4 and len(set(recent_moves[-4:])) <= 2 and len(valid_moves) > 1:
                # Elige un movimiento aleatorio válido que NO sea el último que causó el bucle
                chosen_move = random.choice([m for m in valid_moves if m != recent_moves[-1]])
                print(f"🔄 ¡Alerta de bucle de vaivén! Rompiendo con movimiento impredecible: {chosen_move}")
                recent_moves.clear()
            else:
                # Selección adaptativa normal según la esquina dominante actual
                chosen_move = None
                for move in strategic_order:
                    if move in valid_moves:
                        chosen_move = move
                        break
            
            # Guardar en el historial de movimientos ejecutados
            recent_moves.append(chosen_move)
            if len(recent_moves) > 10:
                recent_moves.pop(0)
            
            # 6. Enviar comando e introducir delay para suavizar el render del navegador
            send_key(driver, chosen_move)
            time.sleep(0.15)
            
        except Exception as e:
            print(f"⚠️ Error: {e}. Reabriendo Selenium...")
            try: driver.quit()
            except: pass
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            driver.get("data:text/html," + html)
            time.sleep(2)
            driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(1)

if __name__ == "__main__":
    main()