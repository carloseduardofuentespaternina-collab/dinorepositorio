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
# CONFIGURACIÓN CHROME (AZURE / LOCAL)
# =========================
chrome_options = Options()
chrome_options.add_argument("--headless")        # Comenta esta línea si quieres ver la ventana del navegador
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
# BUCLE PRINCIPAL CON ANTI-BLOQUEO
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
    
    # Estrategia base para arrinconar fichas abajo a la izquierda
    moves_order = ["LEFT", "DOWN", "RIGHT", "UP"]
    
    while True:
        try:
            board = get_board(driver)
            if not board or all(v == 0 for row in board for v in row):
                time.sleep(0.1)
                continue
            
            # 1. Detectar Game Over real en la pantalla
            if driver.find_elements(By.CLASS_NAME, "game-over") and driver.find_element(By.CLASS_NAME, "game-over").is_displayed():
                print("💀 Game Over oficial detectado. Reiniciando partida...")
                restart_game(driver)
                last_board = None
                consecutive_no_change = 0
                last_progress_time = time.time()
                continue
            
            # 2. Control de progreso (Límite tolerante de 40s para evitar reinicios innecesarios en puntajes altos)
            current_max = max(max(row) for row in board)
            if current_max > last_max_tile:
                last_max_tile = current_max
                last_progress_time = time.time()
            elif time.time() - last_progress_time > 40:
                print("⏱️ Sin progreso en la ficha máxima durante 40 segundos. Reiniciando...")
                restart_game(driver)
                last_max_tile = 0
                last_progress_time = time.time()
                last_board = None
                continue
            
            # 3. Intentar movimientos en orden de prioridad estratégica
            move_executed = False
            for move in moves_order:
                send_key(driver, move)
                time.sleep(0.12)  # Tiempo crucial para que la animación termine en el navegador
                
                new_board = get_board(driver)
                if new_board != board:
                    last_board = new_board
                    move_executed = True
                    consecutive_no_change = 0  # Reseteamos contador de bloqueos
                    break  # Continuamos con el bucle principal y el nuevo tablero
            
            # 4. SISTEMA DE DESATASCO AGRESIVO (Para situaciones extremas)
            if not move_executed:
                consecutive_no_change += 1
                print(f"⚠️ Tablero estático. Activando protocolo de desatasco ({consecutive_no_change}/5)")
                
                if consecutive_no_change >= 5:
                    print("❌ El tablero está completamente bloqueado sin movimientos legales. Forzando reinicio...")
                    restart_game(driver)
                    last_board = None
                    consecutive_no_change = 0
                    continue
                
                # Si la estrategia normal falló por completo, probamos todas las direcciones de forma exhaustiva
                emergency_moves = ["UP", "RIGHT", "DOWN", "LEFT"]
                for emergency_move in emergency_moves:
                    send_key(driver, emergency_move)
                    time.sleep(0.12)
                    new_board = get_board(driver)
                    if new_board != board:
                        print(f"🔓 Desatascado con éxito usando movimiento de emergencia: {emergency_move}")
                        last_board = new_board
                        move_executed = True
                        consecutive_no_change = 0
                        break
            
            # Pequeña pausa de estabilidad antes del próximo ciclo
            time.sleep(0.05)
            
        except Exception as e:
            print(f"⚠️ Error en el bucle: {e}. Recomenzando driver de Selenium...")
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