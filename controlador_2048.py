import time
import requests
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
# CONFIGURACIÓN CHROME (AZURE)
# =========================
chrome_options = Options()
chrome_options.add_argument("--headless")        # Comenta para ver ventana
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

# =========================
# BUCLE PRINCIPAL CON ESTRATEGIA DE ESQUINA
# =========================
def main():
    html = get_local_game_html()
    if not html:
        return
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get("data:text/html," + html)
    time.sleep(2)
    driver.find_element(By.TAG_NAME, "body").click()
    print("🚀 Bot iniciado. Estrategia: mantener esquina inferior izquierda.")
    
    last_board = None
    consecutive_no_change = 0
    last_max_tile = 0
    last_progress_time = time.time()
    
    while True:
        try:
            board = get_board(driver)
            if not board or all(v == 0 for row in board for v in row):
                time.sleep(0.2)
                continue
            
            # Detectar Game Over
            if driver.find_elements(By.CLASS_NAME, "game-over") and driver.find_element(By.CLASS_NAME, "game-over").is_displayed():
                print("💀 Game Over. Reiniciando...")
                restart_game(driver)
                last_board = None
                consecutive_no_change = 0
                last_progress_time = time.time()
                continue
            
            # Control de progreso: si la ficha máxima no aumenta en 20 segundos, reiniciar
            current_max = max(max(row) for row in board)
            if current_max > last_max_tile:
                last_max_tile = current_max
                last_progress_time = time.time()
            elif time.time() - last_progress_time > 20:
                print("⏱️ Sin progreso en 20 segundos. Reiniciando...")
                restart_game(driver)
                last_max_tile = 0
                last_progress_time = time.time()
                last_board = None
                continue
            
            # Si el tablero no cambió después de 3 movimientos, reiniciar (evita bloqueo)
            if last_board is not None and board == last_board:
                consecutive_no_change += 1
                if consecutive_no_change >= 3:
                    print("⚠️ Tablero congelado. Reiniciando...")
                    restart_game(driver)
                    consecutive_no_change = 0
                    last_board = None
                    continue
            else:
                consecutive_no_change = 0
            
            # ESTRATEGIA GANADORA: priorizar IZQUIERDA, luego ABAJO, luego DERECHA, luego ARRIBA
            # Esta secuencia compacta las fichas hacia la esquina inferior izquierda.
            moves_order = ["LEFT", "DOWN", "RIGHT", "UP"]
            move_executed = False
            
            for move in moves_order:
                send_key(driver, move)
                # Esperar hasta 0.3 segundos a que el tablero cambie
                start_wait = time.time()
                while time.time() - start_wait < 0.3:
                    new_board = get_board(driver)
                    if new_board != board:
                        move_executed = True
                        last_board = new_board
                        break
                    time.sleep(0.03)
                if move_executed:
                    break
            
            if not move_executed:
                # Esto no debería ocurrir, pero por si acaso reiniciamos
                print("❌ Ningún movimiento cambió el tablero. Reiniciando...")
                restart_game(driver)
                last_board = None
            
            # Pequeña pausa entre movimientos
            time.sleep(0.05)
            
        except Exception as e:
            print(f"⚠️ Error: {e}. Recuperando driver...")
            driver.quit()
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            driver.get("data:text/html," + html)
            time.sleep(2)
            driver.find_element(By.TAG_NAME, "body").click()
            time.sleep(1)

if __name__ == "__main__":
    main()