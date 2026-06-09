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
    driver.get("https://chromedino.com")
    driver.maximize_window()
    
    # 1. Esperar a que el juego cargue
    WebDriverWait(driver, 30).until(
        lambda d: d.execute_script("return typeof Runner !== 'undefined'")
    )
    
    # 2. Iniciar el juego
    body = driver.find_element(By.TAG_NAME, "body")
    body.send_keys(Keys.SPACE)
    print("Juego iniciado. Controlando por simulación de hardware nativo...")
    time.sleep(1)

    timeout_seguridad = time.time() + 90
    score = 0

    # 3. Bucle de alto rendimiento controlado por Python
    while score < 500 and time.time() < timeout_seguridad:
        
        # Leemos los datos esenciales mediante consultas seguras de solo lectura
        datos_juego = driver.execute_script("""
            if (typeof Runner === 'undefined' || !Runner.instance_) return null;
            return {
                score: Runner.instance_.distanceRan,
                hasObstacles: Runner.instance_.horizon.obstacles.length > 0,
                xPos: Runner.instance_.horizon.obstacles.length > 0 ? Runner.instance_.horizon.obstacles[0].xPos : -1,
                speed: Runner.instance_.currentSpeed
            };
        """)

        if datos_juego:
            score = datos_juego['score']
            
            # Si hay un obstáculo en pantalla
            if datos_juego['hasObstacles']:
                x_pos = datos_juego['xPos']
                velocidad = datos_juego['speed']
                
                # Distancia de salto adaptativa segura
                distancia_limite = 23 * velocidad
                
                # Si el cactus entra en la zona de peligro, enviamos la señal física de salto
                if 0 < x_pos < distancia_limite:
                    body.send_keys(Keys.SPACE)
                    # Pausa estratégica pequeña para evitar enviar múltiples saltos por el mismo cactus
                    time.sleep(0.18) 

        # Tasa de muestreo óptima para evitar sobrecargar la memoria de Chromedriver
        time.sleep(0.01)

    print(f"Ciclo terminado. Puntaje final alcanzado: {int(score)}")
    
    if score >= 500:
        print("¡Meta de 500 puntos superada con éxito!")
        driver.execute_script("if(Runner.instance_) Runner.instance_.gameOver();")

    assert score >= 500, f"Error: El juego se detuvo en {int(score)} puntos."
    print("Prueba finalizada con éxito total en Azure DevOps.")

except Exception as e:
    print(f"Error detectado en la ejecución: {e}")
    raise
finally:
    driver.quit()
