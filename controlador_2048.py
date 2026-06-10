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
                parts = position_class[0].split("-")
                col, row = int(parts[2]), int(parts[3])
                value = int(value_class[0].split("-")[1])
                tiles[(col, row)] = value
    except Exception:
        pass
    return tiles

def max_tile(driver):
    """Retorna el valor máximo actual en el tablero."""
    board = get_board(driver)
    return max(board.values()) if board else 0

try:
    print("Conectando al juego 2048...")
    driver.get("https://play2048.co/")
    time.sleep(3)

    body = driver.find_element(By.TAG_NAME, "body")
    print("Juego iniciado — Meta: llegar a 256\n")

    estrategia_esquina = [
        Keys.LEFT,
        Keys.DOWN,
        Keys.RIGHT,
        Keys.UP,
    ]

    ultimo_movimiento = 0
    META = 256  # ✅ Cambia este valor si quieres otra meta

    for i in range(2000):
        key = estrategia_esquina[ultimo_movimiento % len(estrategia_esquina)]
        body.send_keys(key)
        ultimo_movimiento += 1

        if i % 100 == 0:
            actual = max_tile(driver)
            print(f"Movimiento: {i} | Tile máximo: {actual}")

        time.sleep(0.05)

        # ✅ Detectar tile 256 (victoria personalizada)
        actual = max_tile(driver)
        if actual >= META:
            print(f"\n🏆 ¡META ALCANZADA! Llegaste a {actual} en el movimiento {i}")
            break

        # Detectar Game Over
        game_over = driver.find_elements(By.CLASS_NAME, "game-over")
        if game_over:
            print(f"\n💀 Game Over en movimiento {i} | Tile máximo: {actual}")
            break

        # Detectar victoria oficial (2048)
        winner = driver.find_elements(By.CLASS_NAME, "game-won")
        if winner:
            print("¡Ganaste oficialmente! Llegaste a 2048 🎉")
            break

    print("\nPrueba finalizada con éxito")

except Exception as e:
    print(f"Error en la ejecución: {e}")
    raise

finally:
    time.sleep(5)
    driver.quit()