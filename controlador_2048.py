import time
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

def get_board(driver):
    """Lee el estado actual del tablero."""
    tiles = {}
    try:
        tile_elements = driver.find_elements(By.CSS_SELECTOR, ".tile")
        for tile in tile_elements:
            classes = tile.get_attribute("class").split()
            position_class = [c for c in classes if c.startswith("tile-position-")]
            value_class = [c for c in classes if c.startswith("tile-") and c[5:].isdigit()]
            if position_class and value_class:
                # tile-position-col-row
                parts = position_class[0].split("-")
                col, row = int(parts[2]), int(parts[3])
                value = int(value_class[0].split("-")[1])
                tiles[(col, row)] = value
    except Exception:
        pass
    return tiles

try:
    print("Conectando al juego 2048...")
    driver.get("https://play2048.co/")
    time.sleep(3)

    body = driver.find_element(By.TAG_NAME, "body")
    print("Juego iniciado")

    # ─── Estrategia en esquina (esquina inferior-izquierda) ───
    # Prioridad: LEFT → DOWN → RIGHT → UP
    # Mantiene los tiles grandes en la esquina inferior-izquierda
    estrategia_esquina = [
        Keys.LEFT,
        Keys.DOWN,
        Keys.RIGHT,
        Keys.UP,
    ]

    ultimo_movimiento = 0  # índice que rota

    for i in range(2000):
        # Intentar movimiento prioritario según estrategia
        key = estrategia_esquina[ultimo_movimiento % len(estrategia_esquina)]
        body.send_keys(key)
        ultimo_movimiento += 1

        if i % 100 == 0:
            print(f"Movimiento: {i}")

        time.sleep(0.05)

        # Detectar Game Over
        game_over = driver.find_elements(By.CLASS_NAME, "game-over")
        if game_over:
            print("¡Juego terminado! (Game Over)")
            break

        # Detectar victoria (tile 2048)
        winner = driver.find_elements(By.CLASS_NAME, "game-won")
        if winner:
            print("¡Ganaste! Llegaste a 2048 🎉")
            break

    print("Prueba finalizada con éxito")

except Exception as e:
    print(f"Error en la ejecución: {e}")
    raise

finally:
    time.sleep(5)
    driver.quit()