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

# ==========================================
# ELIMINAR ANUNCIOS E INTERFERENCIAS (DOM)
# ==========================================
def clean_ads(driver):
    """Borra elementos sospechosos de publicidad que rompen el lector de fichas"""
    script = """
    var iframe = document.getElementsByTagName('iframe');
    while(iframe.length > 0){
        iframe[0].parentNode.removeChild(iframe[0]);
    }
    var ads = document.querySelectorAll('[id*="google"], [class*="ads"], [class*="banner"]');
    ads.forEach(function(el) { el.remove(); });
    """
    try:
        driver.execute_script(script)
    except:
        pass

# ==========================================
# OBTENER TABLERO CON JS (BLINDADO)
# ==========================================
def get_board(driver):
    script = """
    var board = [[0,0,0,0],[0,0,0,0],[0,0,0,0],[0,0,0,0]];
    var tiles = document.getElementsByClassName('tile');
    for (var i = 0; i < tiles.length; i++) {
        var tile = tiles[i];
        if (!tile.innerText || tile.offsetParent === null) continue; 
        
        var value = parseInt(tile.innerText.replace(/\\D/g, ''));
        if (isNaN(value)) continue;

        var classes = tile.className;
        var match = classes.match(/tile-position-(\\d+)-(\\d+)/);
        if (match) {
            var col = parseInt(match[1]) - 1;
            var row = parseInt(match[2]) - 1;
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
# BUCLE PRINCIPAL CON ANTI-INERCIA
# ==========================================
def main():
    html = get_local_game_html()
    if not html:
        return
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get("data:text/html," + html)
    time.sleep(2)
    clean_ads(driver)
    driver.find_element(By.TAG_NAME, "body").click()
    print("🚀 Bot Anti-Inercia Iniciado. Objetivo rápido: 256.")
    
    last_max_tile = 0
    last_progress_time = time.time()
    
    # Historial de teclas consecutivas para romper el desuso de LEFT/DOWN
    recent_keys = []
    stuck_counter = 0
    last_flat_board = None

    # Forzar una estrategia híbrida robusta (Prioriza agrupar, pero permite destrabar)
    strategic_order = ["RIGHT", "UP", "LEFT", "DOWN"]

    while True:
        try:
            board = get_board(driver)
            if not board or all(v == 0 for row in board for v in row):
                time.sleep(0.1)
                continue
            
            # Condición de Victoria en 256
            current_max = max(max(row) for row in board)
            if current_max >= 256:
                print(f"🎉 ¡VICTORIA! Se alcanzó la ficha {current_max} de forma limpia.")
                driver.quit()
                break
            
            # Game Over Real
            if driver.find_elements(By.CLASS_NAME, "game-over") and driver.find_element(By.CLASS_NAME, "game-over").is_displayed():
                print("💀 Game Over. Reiniciando...")
                restart_game(driver)
                last_progress_time = time.time()
                last_max_tile = 0
                recent_keys.clear()
                continue
            
            # Control de reinicio por congelamiento total (45s)
            if current_max > last_max_tile:
                last_max_tile = current_max
                last_progress_time = time.time()
            elif time.time() - last_progress_time > 45:
                print("⏱️ Tiempo límite sin combinación estructural. Reiniciando...")
                restart_game(driver)
                last_max_tile = 0
                last_progress_time = time.time()
                recent_keys.clear()
                continue

            # Monitorear si el tablero físicamente no altera sus valores
            board_flat = tuple(v for row in board for v in row)
            if board_flat == last_flat_board:
                stuck_counter += 1
            else:
                stuck_counter = max(0, stuck_counter - 1)
            last_flat_board = board_flat

            # Calcular movimientos físicamente válidos
            valid_moves = [move for move in strategic_order if simulate_move(board, move) != board]
            
            if not valid_moves:
                print("⚠️ Sin movimientos legales. Reiniciando...")
                restart_game(driver)
                last_progress_time = time.time()
                last_max_tile = 0
                recent_keys.clear()
                continue

            # ==========================================================
            # CORRECCIÓN DE COMPORTAMIENTO: OBLIGAR MOVIMIENTOS EVITADOS
            # ==========================================================
            # Si en los últimos 4 movimientos el bot usó solo RIGHT/UP y el tablero está estancándose...
            if len(recent_keys) >= 4 and all(k in ["RIGHT", "UP"] for k in recent_keys[-4:]):
                # Filtramos para obligarlo a usar LEFT o DOWN si son físicamente posibles
                forced_moves = [m for m in valid_moves if m in ["LEFT", "DOWN"]]
                if forced_moves:
                    chosen_move = forced_moves[0]
                    print(f"🛠️ Forzando uso de tecla evitada para limpiar tablero: {chosen_move}")
                else:
                    chosen_move = random.choice(valid_moves)
            
            # Si hay un atasco duro por repetición numérica, ráfaga aleatoria pura
            elif stuck_counter >= 6 and len(valid_moves) > 1:
                print("🚨 Atasco por vaivén detectado. Rompiendo con dirección opuesta...")
                chosen_move = random.choice([m for m in valid_moves if m not in recent_keys[-2:]])
                stuck_counter = 0
            else:
                # Selección estratégica fluida normal
                chosen_move = None
                for move in strategic_order:
                    if move in valid_moves:
                        chosen_move = move
                        break

            # Guardar historial de movimientos ejecutados
            recent_keys.append(chosen_move)
            if len(recent_keys) > 10:
                recent_keys.pop(0)

            # Ejecutar e inyectar limpieza de anuncios en paralelo para asegurar el DOM
            send_key(driver, chosen_move)
            if random.random() < 0.1:  # Limpia anuncios cada 10 movimientos de forma silenciosa
                clean_ads(driver)
            time.sleep(0.13)  
            
        except Exception as e:
            print(f"⚠️ Error: {e}. Reajustando entorno Selenium...")
            try: driver.quit()
            except: pass
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            driver.get("data:text/html," + html)
            time.sleep(2)
            clean_ads(driver)
            driver.find_element(By.TAG_NAME, "body").click()

if __name__ == "__main__":
    main()