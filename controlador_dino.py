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
    
   
    while True:
      
        driver.execute_script("""
            const juego = Runner.instance_;
            if (!juego) return;

            // Guardamos la función original de actualización
            const originalUpdate = juego.update;

            // Sobrescribimos el ciclo de renderizado
            juego.update = function() {
                // Ejecutamos primero la lógica normal del juego
                originalUpdate.apply(this, arguments);
                
                // Si hay obstáculos en pantalla y el tRex NO está saltando actualmente
                if (this.horizon.obstacles.length > 0 && !this.tRex.jumping) {
                    
                    // Tomamos el primer obstáculo de la fila de forma correcta
                    const obstaculo = this.horizon.obstacles[0];
                    
                    // Condición de distancia óptima basada en la velocidad actual del juego
                    const distanciaSalto = 25 * this.currentSpeed; 
                    
                    if (obstaculo.xPos < distanciaSalto && obstaculo.xPos > 0) {
                        // Forzamos el salto nativo simulando el evento del juego
                        // Esto evita alterar el estado gráfico y mantiene al dinosaurio visible
                        juego.onKeyDown({keyCode: 32, type: "keydown"});
                    }
                }
            };
        }
        activarAutopiloto();
        """)
        
    
        score = driver.execute_script("return Runner.instance_.distanceRan")
        
        if score >= 2000:
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
