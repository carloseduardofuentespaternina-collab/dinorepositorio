import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
import time

# 1. Configuración limpia de opciones de Chrome
chrome_options = Options()

# Ocultamos las banderas de automatización para evitar bloqueos en la web
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)

# ¡ELIMINAMOS EL MODO HEADLESS!
# Ya no usamos "if os.getenv('TF_BUILD'):" para que siempre abra la ventana visual

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()), 
    options=chrome_options
)

# Elimina la propiedad de automatización en el navegador antes de abrir la web
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
})
try:
   
    print("Conectando al juego en la web...")
    driver.get("https://chromedino.com/")
    
 
    WebDriverWait(driver, 10).until(
        lambda d: d.execute_script("return typeof Runner !== 'undefined'")
    )
    

    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.SPACE)
    print("Juego iniciado. Controlando...")
    
    score=0
    while score<500:
      
        driver.execute_script("""
            var inst = Runner.instance_;
            if (inst.horizon.obstacles.length > 0) {
                var obs = inst.horizon.obstacles[0];
                if (obs.xPos < 120 && obs.xPos > 0) {
                    inst.tRex.startJump();
                }
            }
        """)
        
    
        score = driver.execute_script("return Runner.instance_.distanceRan")
        
        if score >= 500:
            print(f"Meta alcanzada: {int(score)}. Finalizando prueba.")
      
            driver.execute_script("Runner.instance_.gameOver()")
            break
            
        time.sleep(0.05)


    assert score >= 500, f"Error: El juego terminó antes de tiempo con {score} puntos."
    print("Prueba finalizada con éxito en Azure.")

except Exception as e:
    print(f"Error en la ejecución: {e}")
    raise
finally:
    driver.quit()
