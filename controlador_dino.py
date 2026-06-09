import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


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

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)

# Oculta navigator.webdriver
driver.execute_cdp_cmd(
    "Page.addScriptToEvaluateOnNewDocument",
    {
        "source": """
        Object.defineProperty(
            navigator,
            'webdriver',
            {get: () => undefined}
        );
        """
    }
)

try:

    print("Conectando al juego...")

    driver.get("https://chromedino.com/")

    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script(
            "return typeof Runner !== 'undefined'"
        )
    )

    body = driver.find_element(By.TAG_NAME, "body")

    
    body.send_keys(Keys.SPACE)

    print("Juego iniciado.")

    score = 0

    while score < 5000:

        jump = driver.execute_script("""
            var inst = Runner.instance_;

            if (
                inst.horizon.obstacles.length > 0 &&
                !inst.tRex.jumping &&
                !inst.crashed
            ) {

                var obs = inst.horizon.obstacles[0];

                return (
                    obs.xPos < 120 &&
                    obs.xPos > 0
                );
            }

            return false;
        """)

        if jump:
            body.send_keys(Keys.SPACE)

        score = driver.execute_script(
            "return Runner.instance_.distanceRan"
        )

        if int(score) % 500 == 0 and score > 0:
            print(f"Puntaje: {int(score)}")

        if score >= 5000:
            print(
                f"Meta alcanzada: {int(score)}. Finalizando."
            )

            driver.execute_script(
                "Runner.instance_.gameOver()"
            )
            break

        time.sleep(0.02)

    assert score >= 500, (
        f"Error: el juego terminó antes de tiempo "
        f"con {score} puntos."
    )

    print("Prueba finalizada con éxito.")

except Exception as e:
    print(f"Error en la ejecución: {e}")
    raise

finally:
    driver.quit()