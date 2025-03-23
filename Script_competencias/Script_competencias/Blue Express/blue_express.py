from playwright.sync_api import Playwright, sync_playwright, expect
import pandas as pd
import logging
from datetime import datetime
import os
from sqlalchemy import create_engine
import time

# Configuración de la conexión a PostgreSQL
db_user = "usr_postbi"
db_password = ""
db_host = "10.200.40.10"  # Ejemplo: 'localhost' o '127.0.0.1'
db_port = "5432"  # Puerto por defecto de PostgreSQL
db_name = "DWHP_WEBSCRAP"
db_table = "ft_precios_compe"

# Crear la conexión usando SQLAlchemy
engine = create_engine(f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")



log_file_path = os.path.join(os.path.dirname(__file__), "logs_blue_express.log")
# Configuración del logging
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')


def login(page, email, password):
    try:
        # Intentar cargar la página con un timeout de 30 segundos
        page.goto("https://app.bluex.cl/", timeout=30000)
    except TimeoutError:
    # Si ocurre un timeout, registrar un mensaje de advertencia y continuar
        logging.warning("La página no cargó completamente dentro del tiempo esperado. Continuando con el estado actual.")
    
    page.locator("[data-test=\"login-with-password\"]").click()
    
    # Esperar a que el campo de correo electrónico esté disponible
    page.wait_for_selector('input[placeholder="ejemplo@mail.com"]')
    page.get_by_placeholder("ejemplo@mail.com").fill(email)
    
    # Llenar el campo de contraseña
    page.get_by_placeholder("Introduce contraseña").fill(password)
    
    # Hacer clic en el botón de "Ingresar"
    page.get_by_role("button", name="Ingresar").click()
    
    # Esperar a que la página cargue completamente después del login
    page.get_by_role("button", name="Cotización").click()

def cotizar_envio(page, abreviatura_origen, abreviatura_destino):
    """Nueva lógica de cotización usando abreviaturas"""
    try:
        page.wait_for_timeout(800)
        # Seleccionar origen usando la abreviatura
        page.get_by_label("Origen :OrigenAlgarroboAlhué").select_option(value=abreviatura_origen)
        page.wait_for_timeout(800)
        # Seleccionar destino usando la abreviatura
        page.get_by_label("Destino :DestinoAlgarroboAlhu").select_option(value=abreviatura_destino)
        page.wait_for_timeout(800)
        # Esperar a que el botón de cotización esté visible y habilitado
        page.wait_for_selector('button:has-text("Cotizar")', state="visible", timeout=10000)
        
        # Hacer clic en el botón de cotización
        page.get_by_role("button", name="Cotizar").click()

        page.wait_for_timeout(1500)
        # Esperar a que los precios se carguen
        page.wait_for_selector('div.bx-quoter_shipping-table-prices', timeout=15000)
        
        # Extraer los precios de Sucursal y Domicilio
        precios_sucursal = page.locator('div.bx-quoter_shipping-table-prices_row').nth(0).locator('span.bx-quoter_fixed-container').all_text_contents()
        precios_domicilio = page.locator('div.bx-quoter_shipping-table-prices_row').nth(1).locator('span.bx-quoter_fixed-container').all_text_contents()
        
        # Limpiar los precios y eliminar caracteres no numéricos
        precios_sucursal = [int(precio.replace("$", "").replace(".", "").strip()) for precio in precios_sucursal]
        precios_domicilio = [int(precio.replace("$", "").replace(".", "").strip()) for precio in precios_domicilio]
        
        # Verificar que ambas listas tengan exactamente 4 elementos (XS, S, M, L)
        if len(precios_sucursal) != 4 or len(precios_domicilio) != 4:
            logging.error(f"Precios incompletos: Sucursal={precios_sucursal}, Domicilio={precios_domicilio}")
            raise ValueError("Faltan precios para algunos tamaños.")
        
        # Registrar los precios para depuración
        logging.info(f"Precios extraídos - Sucursal: {precios_sucursal}, Domicilio: {precios_domicilio}")
        
        # Mapeo de tamaños según nuevo orden
        return {
            "XS": {"Sucursal": precios_sucursal[0], "Domicilio": precios_domicilio[0]},
            "S": {"Sucursal": precios_sucursal[1], "Domicilio": precios_domicilio[1]},
            "M": {"Sucursal": precios_sucursal[2], "Domicilio": precios_domicilio[2]},
            "L": {"Sucursal": precios_sucursal[3], "Domicilio": precios_domicilio[3]}
        }
    except Exception as e:
        logging.error(f"Error al cotizar envío: {str(e)}")
        return {}

def run(playwright: Playwright, email, password, combinaciones_path):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    
    try:
        login(page, email, password)
        combinaciones = pd.read_csv(combinaciones_path)
        resultados = []
        
        for _, fila in combinaciones.iterrows():
            intentos = 0
            exito = False
            while intentos < 3 and not exito:
                try:
                    # Usar abreviaturas en lugar de IDs
                    precios = cotizar_envio(page, fila["Abreviatura Origen"], fila["Abreviatura Destino"])
                    
                    for tamano, precios_tamano in precios.items():
                        resultados.append({
                            "rut": "96.938.840-5",
                            "origen": fila["Comuna Origen"],
                            "destino": fila["Comuna Destino"],
                            "tamaño": tamano,
                            "sucursal": precios_tamano["Sucursal"],
                            "domicilio": precios_tamano["Domicilio"],
                            "fecha": datetime.now().strftime("%Y-%m-%d")
                        })
                        logging.info(f"{fila['Comuna Origen']} -> {fila['Comuna Destino']} | {tamano}: Sucursal=${precios_tamano['Sucursal']}, Domicilio=${precios_tamano['Domicilio']}")
                    
                    # Espera entre consultas para evitar bloqueos
                    page.wait_for_timeout(2000)
                    exito = True
                    
                except Exception as e:
                    intentos += 1
                    logging.error(f"Error procesando {fila['Comuna Origen']}-{fila['Comuna Destino']} en intento {intentos}: {str(e)}")
                    if intentos < 3:
                        logging.info("Reiniciando scraping...")
                        context.close()
                        browser.close()
                        browser = playwright.chromium.launch(headless=True)
                        context = browser.new_context()
                        page = context.new_page()
                        login(page, email, password)
        
        # Guardar resultados
        # Subir el DataFrame a PostgreSQL
        
        time.sleep(1)
        resultados_df = pd.DataFrame(resultados)
        time.sleep(2)
        resultados_df.drop_duplicates(inplace=True)
        resultados_df["orden_original"] = resultados_df.index.astype(int)
        resultados_df["fx_insert"] = datetime.now()
        
        time.sleep(3)
        resultados_df.to_sql(db_table, engine, if_exists="append", index=False)

        logging.info("Resultados guardados en la base de datos")
        
    finally:
        context.close()
        browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(
            playwright,
            email="benjamin.e.p.gaspar@gmail.com",
            password="CorreosChile1234",
            combinaciones_path= os.path.join(os.path.dirname(__file__), "combinaciones_origen_destino.csv")
        )