import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# Configuración de Chrome
chrome_options = Options()

chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option(
    "excludeSwitches",
    ["enable-automation"]
)
chrome_options.add_experimental_option(
    "useAutomationExtension",
    False
)

# Abrir Chrome
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)

try:

    print("Conectando al juego 2048...")

    driver.get("https://play2048.co/")

    time.sleep(3)

    body = driver.find_element(By.TAG_NAME, "body")

    print("Juego iniciado")

    movimientos = [
        Keys.UP,
        Keys.RIGHT,
        Keys.UP,
        Keys.RIGHT
    ]

    for i in range(2000):

        body.send_keys(
            movimientos[i % len(movimientos)]
        )

        if i % 100 == 0:
            print(f"Movimiento: {i}")

        # Detectar Game Over
        game_over = driver.find_elements(
            By.CLASS_NAME,
            "game-over"
        )

        if game_over:
            print("Juego terminado")
            break

        time.sleep(0.05)

    print("Prueba finalizada con éxito")

except Exception as e:
    print(f"Error en la ejecución: {e}")
    raise

finally:
    time.sleep(5)
    driver.quit()