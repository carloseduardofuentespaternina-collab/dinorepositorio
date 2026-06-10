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
    script = """
    var iframe = document.getElementsByTagName('iframe');
    while(iframe.length > 0){
        iframe[0].parentNode.removeChild(iframe[0]);
    }
    var ads = document.querySelectorAll('[id*="google"], [class*="ads"], [class*="banner"]');
    ads.forEach(function(el) { el.remove(); });
    """
    try: driver.execute_script(script)
    except: pass

# ==========================================
# OBTENER TABLERO Y SCORE CON JS
# ==========================================
def get_game_state(driver):
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
    
    // Obtener puntuación actual
    var score = 0;
    var scoreContainer = document.getElementsByClassName('score-container')[0];
    if (scoreContainer) {
        // Nos quedamos solo con el primer número antes de cualquier texto de "+4"
        var scoreText = scoreContainer.innerText.split('\\n')[0];
        score = parseInt(scoreText.replace(/\\D/g, '')) || 0;
    }

    return {board: board, score: score};
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
# EVALUADOR DE MEJOR MOVIMIENTO EQUILIBRADO
# ==========================================
def evaluate_best_move(board, valid_moves):
    """Evalúa cuál movimiento genera más espacios vacíos (más fusiones)"""
    best_move = valid_moves[0]
    max_empty = -1
    
    # Buscamos qué movimiento deja más ceros en el tablero simulado
    for move in valid_moves:
        simulated = simulate_move(board, move)
        empty_cells = sum(row.count(0) for row in simulated)
        if empty_cells > max_empty:
            max_empty = empty_cells
            best_move = move
            
    return best_move

# ==========================================
# BUCLE PRINCIPAL CORREGIDO
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
    print("🚀 Bot de Movimiento Libre Iniciado. Monitoreo por Score activo (Meta: 256).")
    
    last_score = 0
    no_score_inc_counter = 0
    last_max_tile = 0
    last_progress_time = time.time()

    # Todas las direcciones tienen el mismo derecho a ser usadas
    all_directions = ["LEFT", "DOWN", "RIGHT", "UP"]

    while True:
        try:
            state = get_game_state(driver)
            board = state["board"]
            current_score = state["score"]

            if not board or all(v == 0 for row in board for v in row):
                time.sleep(0.1)
                continue
            
            # Condición de Victoria en 256
            current_max = max(max(row) for row in board)
            if current_max >= 256:
                print(f"🎉 ¡VICTORIA ESTRUCTURAL! Alcanzada la ficha {current_max}.")
                driver.quit()
                break
            
            # Game Over Real
            if driver.find_elements(By.CLASS_NAME, "game-over") and driver.find_element(By.CLASS_NAME, "game-over").is_displayed():
                print("💀 Game Over. Reiniciando...")
                restart_game(driver)
                last_score = 0
                no_score_inc_counter = 0
                last_progress_time = time.time()
                continue
            
            # Control de tiempo límite por congelamiento (45s)
            if current_max > last_max_tile:
                last_max_tile = current_max
                last_progress_time = time.time()
            elif time.time() - last_progress_time > 45:
                print("⏱️ Tablero congelado por tiempo. Reiniciando...")
                restart_game(driver)
                last_max_tile = 0
                last_score = 0
                no_score_inc_counter = 0
                last_progress_time = time.time()
                continue

            # CONTADOR DE ATASCO BASADO EN SCORE REAL
            if current_score == last_score:
                no_score_inc_counter += 1
            else:
                no_score_inc_counter = 0 # Restablecer si el score sube
            last_score = current_score

            # Calcular qué movimientos cambian realmente el tablero
            valid_moves = [move for move in all_directions if simulate_move(board, move) != board]
            
            if not valid_moves:
                print("⚠️ Sin movimientos disponibles. Reiniciando...")
                restart_game(driver)
                last_score = 0
                no_score_inc_counter = 0
                continue

            # ==========================================================
            # ACTIVACIÓN INMEDIATA DEL ALEATORIO POR FALTA DE SCORE
            # ==========================================================
            if no_score_inc_counter >= 6 and len(valid_moves) > 1:
                # Si lleva 6 movimientos moviendo piezas sin sumar puntos, está en vaivén.
                # Elegimos uno aleatorio de la lista de válidos para destrabar las esquinas.
                chosen_move = random.choice(valid_moves)
                print(f"🔄 ¡Vaivén detectado por Score! Forzando movimiento aleatorio: {chosen_move}")
                no_score_inc_counter = 0
            else:
                # Selección inteligente basada en optimización de espacio libre
                chosen_move = evaluate_best_move(board, valid_moves)

            # Ejecutar movimiento
            send_key(driver, chosen_move)
            
            # Limpieza silenciosa de Ads periódica
            if random.random() < 0.05:
                clean_ads(driver)
                
            time.sleep(0.12)  
            
        except Exception as e:
            print(f"⚠️ Error controlado: {e}. Reajustando Selenium...")
            try: driver.quit()
            except: pass
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            driver.get("data:text/html," + html)
            time.sleep(2)
            clean_ads(driver)
            driver.find_element(By.TAG_NAME, "body").click()

if __name__ == "__main__":
    main()