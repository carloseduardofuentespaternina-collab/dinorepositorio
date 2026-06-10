import time
import requests
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ==========================================
# CONFIGURACIÓN E INYECCIÓN DEL JUEGO
# ==========================================
GAME_URL = "https://raw.githubusercontent.com/gabrielecirulli/2048/master/index.html"

def get_local_game_html():
    try:
        response = requests.get(GAME_URL, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"❌ Error descargando juego: {e}")
        return None

chrome_options = Options()
chrome_options.add_argument("--headless")  # Comenta para ver el navegador físicamente
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1024,768")

# ==========================================
# FUNCIONES DE CONTROL DIRECTO DEL DOM
# ==========================================
def send_key(driver, direction):
    """Envía la pulsación de tecla directamente al documento de la página"""
    driver.execute_script(f"""
        var event = new KeyboardEvent('keydown', {{
            key: 'Arrow{direction.title()}',
            code: 'Arrow{direction.title()}',
            bubbles: true
        }});
        document.dispatchEvent(event);
    """)

def get_container_html(driver):
    """Devuelve el HTML crudo del contenedor de fichas para saber si algo mutó en pantalla"""
    try:
        container = driver.find_element(By.CLASS_NAME, "tile-container")
        return container.get_attribute("innerHTML")
    except:
        return ""

def get_current_score(driver):
    """Lee el score directamente de la interfaz del usuario"""
    try:
        score_element = driver.find_element(By.CLASS_NAME, "score-container")
        score_text = score_element.text.split('\n')[0]
        return int(''.join(filter(str.isdigit, score_text)))
    except:
        return 0

def check_256_victory(driver):
    """Busca directamente en el DOM si existe una ficha con el valor 256"""
    try:
        tiles = driver.find_elements(By.CLASS_NAME, "tile")
        for tile in tiles:
            if "tile-256" in tile.get_attribute("className") or tile.text == "256":
                return True
    except:
        pass
    return False

def restart_game(driver):
    try:
        btn = driver.find_element(By.CLASS_NAME, "restart-button")
        btn.click()
        time.sleep(0.5)
    except:
        driver.refresh()
        time.sleep(2)
    driver.find_element(By.TAG_NAME, "body").click()
    print("🔄 Tablero Reiniciado")

# ==========================================
# BUCLE DE FUERZA BRUTA ANTI-ATASCOS
# ==========================================
def main():
    html = get_local_game_html()
    if not html:
        return
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get("data:text/html," + html)
    time.sleep(2)
    driver.find_element(By.TAG_NAME, "body").click()
    print("🚀 NUEVO Bot de Fuerza Bruta DOM Iniciado. Meta: 256.")

    # Patrón de juego clásico equilibrado (Abajo e Izquierda priorizados, pero Derecha/Arriba disponibles)
    base_moves = ["DOWN", "LEFT", "RIGHT", "UP"]
    
    stuck_moves_count = 0
    last_score = 0
    score_stuck_counter = 0

    while True:
        try:
            # 1. Comprobar Victoria Inmediata (Ficha 256)
            if check_256_victory(driver):
                print("🎉 ¡VICTORIA! Ficha 256 detectada visualmente en el navegador.")
                driver.quit()
                break

            # 2. Comprobar Game Over Visual
            if driver.find_elements(By.CLASS_NAME, "game-over") and driver.find_element(By.CLASS_NAME, "game-over").is_displayed():
                print("💀 Game Over detectado en pantalla. Reiniciando...")
                restart_game(driver)
                stuck_moves_count = 0
                score_stuck_counter = 0
                last_score = 0
                continue

            # 3. Control de estancamiento por Puntuación (Score)
            current_score = get_current_score(driver)
            if current_score == last_score and current_score > 0:
                score_stuck_counter += 1
            else:
                score_stuck_counter = 0
            last_score = current_score

            # ==========================================================
            # ACTIVACIÓN CRÍTICA: MODO PÁNICO SEGUIDO (FUERZA BRUTA ALEATORIA)
            # ==========================================================
            if stuck_moves_count >= 4 or score_stuck_counter >= 8:
                print("🚨 ¡Atasco total detectado! Ejecutando ráfaga caótica de desbloqueo...")
                # Lanza 5 movimientos totalmente impredecibles para forzar la agitación de las esquinas
                for _ in range(5):
                    chaos_move = random.choice(base_moves)
                    send_key(driver, chaos_move)
                    time.sleep(0.1)
                stuck_moves_count = 0
                score_stuck_counter = 0
                continue

            # 4. Flujo normal de juego: Intentar movimientos basados en cambios reales del navegador
            moved = False
            for move in base_moves:
                html_before = get_container_html(driver)
                send_key(driver, move)
                time.sleep(0.12)  # Delay para el renderizado de la animación CSS
                html_after = get_container_html(driver)

                # Si el HTML interno de las fichas cambió, significa que el movimiento SÍ fue efectivo
                if html_before != html_after:
                    moved = True
                    stuck_moves_count = 0  # Reseteamos contador de atasco
                    break  # Salimos para iniciar el nuevo ciclo

            # Si recorrió las 4 direcciones y ninguna generó cambios en el navegador...
            if not moved:
                stuck_moves_count += 1
                time.sleep(0.05)

        except Exception as e:
            print(f"⚠️ Alerta en entorno: {e}. Reajustando...")
            try: driver.quit()
            except: pass
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
            driver.get("data:text/html," + html)
            time.sleep(2)
            driver.find_element(By.TAG_NAME, "body").click()

if __name__ == "__main__":
    main()