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
    print("Juego iniciado. Controlando por lectura protegida...")
    time.sleep(1)

    timeout_seguridad = time.time() + 90
    score = 0
    esta_en_el_aire = False

    # 3. Bucle protegido contra congelamientos
    while score < 500 and time.time() < timeout_seguridad:
        try:
            # Consultamos los datos esenciales en una sola línea ultrarrápida
            datos = driver.execute_script("""
                if (typeof Runner === 'undefined' || !Runner.instance_) return null;
                var inst = Runner.instance_;
                var hasObs = inst.horizon.obstacles.length > 0;
                return {
                    score: inst.distanceRan,
                    hasObs: hasObs,
                    xPos: hasObs ? inst.horizon.obstacles[0].xPos : -1,
                    speed: inst.currentSpeed,
                    jumping: inst.tRex.jumping
                };
            """)
            
            if not datos:
                time.sleep(0.1)
                continue

            score = datos['score']
            esta_en_el_aire = datos['jumping']

            # Si hay un obstáculo en pantalla y el dinosaurio está en el suelo
            if datos['hasObs'] and not esta_en_el_aire:
                x_pos = datos['xPos']
                velocidad = datos['speed']
                
                # Distancia óptima según la velocidad del juego
                distancia_limite = 20 * velocidad
                
                # Si el cactus entra en la zona de peligro, ordenamos saltar nativamente
                if 0 < x_pos < distancia_limite:
                    driver.execute_script("Runner.instance_.onKeyDown({keyCode: 32, type: 'keydown'});")
                    # Damos una pequeña pausa para permitir que el motor web procese el inicio del salto
                    time.sleep(0.15) 

        except Exception as script_error:
            # Si el canal se satura momentáneamente, lo ignoramos y continuamos en el siguiente ciclo
            # Esto evita que el pipeline se congele o se caiga
            pass

        # Tasa de muestreo estable para no ahogar al controlador de Chrome
        time.sleep(0.02)

    print(f"Ciclo terminado. Puntaje final alcanzado: {int(score)}")


    assert score >= 500, f"Error: El juego se detuvo en {int(score)} puntos."
    print("Prueba finalizada con éxito total en Azure DevOps.")

except Exception as e:
    print(f"Error detectado en la ejecución: {e}")
    raise
finally:
    driver.quit()
