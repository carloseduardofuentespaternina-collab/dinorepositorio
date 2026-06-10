import time
import random

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager


# =========================
# CONFIGURACIÓN CHROME
# =========================
chrome_options = Options()
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)

try:
    print("Abriendo 2048...")

    driver.get("https://play2048.co/")
    time.sleep(3)

    # =========================
    # IMPORTANTE: DAR FOCO AL JUEGO
    # =========================
    body = driver.find_element(By.TAG_NAME, "body")
    body.click()

    print("Juego iniciado")

    # Movimientos básicos (estrategia simple)
    movimientos = [
        Keys.UP,
        Keys.RIGHT,
        Keys.DOWN,
        Keys.LEFT
    ]

    i = 0

    while True:

        # Enviar movimiento
        body.send_keys(movimientos[i % len(movimientos)])
        i += 1

        # Mostrar progreso
        if i % 50 == 0:
            print(f"Movimientos realizados: {i}")

        # Detectar GAME OVER (más robusto)
        game_over = driver.find_elements(
            By.CSS_SELECTOR,
            ".game-over, .game-message.game-over"
        )

        if game_over:
            print("💀 Juego terminado")
            break

        time.sleep(0.1)

    print("Proceso finalizado")

except Exception as e:
    print(f"Error: {e}")

finally:
    time.sleep(3)
    driver.quit()