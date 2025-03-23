import csv
import logging
import re
from typing import List, Dict
from playwright.sync_api import Playwright, sync_playwright, expect
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import create_engine
import time

db_user = "usr_postbi"
db_password = ""
db_host = "10.200.40.10"  # Ejemplo: 'localhost' o '127.0.0.1'
db_port = "5432"  # Puerto por defecto de PostgreSQL
db_name = "DWHP_WEBSCRAP"
db_table = "ft_precios_compe"

engine = create_engine(f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

# Definir el nombre del archivo CSV con la fecha y hora
log_file = os.path.join(os.path.dirname(__file__),"logs_chile_express_emprendedores.log")
combinaciones_file= os.path.join(os.path.dirname(__file__), "combinaciones_origen_destino_chile_express.csv")
logging.basicConfig(filename=log_file, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)


def read_combinations() -> List[Dict[str, str]]:
    """Lee las combinaciones desde el archivo CSV fijo"""
    combinations = []
    try:
        with open(combinaciones_file, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                combinations.append({
                    'Origen': row['Origen'],
                    'Destino': row['Destino']
                })
        logger.info(f"Combinaciones leídas: {len(combinations)}")
        return combinations
    except Exception as e:
        logger.error(f"Error leyendo CSV: {str(e)}")
        raise

def setup_browser():
    """Configura el navegador y el contexto de Playwright"""
    playwright = sync_playwright().start()
    browser =  playwright.chromium.launch(headless=True)
    context =  browser.new_context()
    return playwright, browser, context

def fill_declared_value(page, value: str):
    """Llena el valor declarado en el formulario"""
    page.get_by_placeholder("Valor declarado (pesos").click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.get_by_placeholder("Valor declarado (pesos").fill(value)

def fill_origin_destination(page, origin: str, destination: str):
    """Llena los campos de origen y destino en el formulario"""
    # Seleccionar origen
    page.get_by_placeholder("origen").click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.get_by_placeholder("origen").fill(origin)
    page.get_by_role("option", name=origin, exact=True).click()

    time.sleep(1.8)
    
    # Seleccionar destino
    page.get_by_placeholder("destino").click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")
    page.get_by_placeholder("destino").fill(destination)
    page.get_by_role("option", name=destination, exact=True).click()

def get_price(page) -> Dict[str, str]:
    """Obtiene precios excluyendo L y XL+ con validaciones mejoradas"""
    prices = {}
    
    try:
        # Esperas estratégicas mejoradas
        time.sleep(1.2)  # Espera inicial optimizada
        page.wait_for_selector('div.card.card-button:has(img.size-icon)', timeout=10000)
        time.sleep(0.8)  # Espera post-carga

        # Selector más específico para tarjetas válidas
        price_cards = page.query_selector_all('div.card.card-button:has(img.size-icon)')
        
        for index, card in enumerate(price_cards):
            try:
                # Espera progresiva entre tarjetas
                time.sleep(index * 0.1)
                
                # Verificación en cascada
                icon = card.query_selector('img.size-icon')
                if not icon:
                    logger.debug("Ícono no encontrado en tarjeta")
                    continue
                
                src = icon.get_attribute('src')
                if not src:
                    logger.debug("Atributo src no encontrado")
                    continue

                # Extracción y normalización de tamaño
                size_match = re.search(r'icon-([a-z-]+)\.svg', src, re.IGNORECASE)
                if not size_match:
                    logger.debug(f"Formato src no válido: {src}")
                    continue
                    
                raw_size = size_match.group(1).upper()
                size = raw_size  # No normalizar XL-PLUS a XL
                
                # Filtrado de tamaños no deseados
                if size in ['L', 'XL-PLUS']:  
                    continue

                # Obtención segura del precio
                price_element = card.query_selector('h6.mb-0.text-xs > span.ng-star-inserted')
                if not price_element:
                    logger.debug(f"Elemento de precio no encontrado para {raw_size}")
                    continue
                    
                price_text = price_element.inner_text()
                if not price_text:
                    logger.debug(f"Texto de precio vacío para {raw_size}")
                    continue
                
                # Guardar precio usando tamaño original (sin normalizar)
                prices[raw_size] = price_text.strip()

            except Exception as card_error:
                logger.warning(f"Error procesando tarjeta {index}: {str(card_error)}")
                continue

        return prices

    except Exception as e:
        logger.error(f"Error crítico: {str(e)}", exc_info=True)
        return {}
        
    except Exception as e:
        logger.error(f"Error obteniendo precios: {str(e)}")
        return {}

def scrape_combination(page, origin: str, destination: str) -> List[Dict[str, str]]:
    """Realiza el scraping para una combinación específica"""
    fill_origin_destination(page, origin, destination)
    time.sleep(2)
    prices = get_price(page)
    results = [{'rut': "99.999.999-9", 'origen': origin, 'destino': destination, 'tamaño': size, 'precio': price} for size, price in prices.items()]
    return results

def timeout_action(func, timeout=10):
    def wrapper():
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                func()
                return
            except Exception as e:
                logger.warning(f"Accion no completada en {timeout} segundos. Reintentando... Error: {str(e)}")
                time.sleep(1)
        logger.warning(f"Accion no completada en {timeout} segundos. Continuando...")
    return wrapper

def main():
    try:
        combinations = read_combinations()
        playwright, browser, context = setup_browser()
        page = context.new_page()
        
        timeout_action(lambda: page.goto("https://emprendedores.chilexpress.cl/cotizar"))()
        
        resultados = []
        fill_declared_value(page, "5000")
        for combo in combinations:
            success = False
            attempts = 0
            while not success and attempts < 3:
                try:
                    time.sleep(3)
                    results = scrape_combination(page, combo['Origen'], combo['Destino'])
                    for result in results:
                        resultados.append(result)
                    logger.info(f"Precios obtenidos: {combo['Origen']} -> {combo['Destino']}: {results}")
                    success = True
                except Exception as e:
                    logger.error(f"Error procesando {combo}: {str(e)}. Reintentando...")
                    page.reload()
                    time.sleep(3)
                    fill_declared_value(page, "5000")
                    attempts += 1
                    time.sleep(5)  # Esperar antes de reintentar

        # Limpiar los signos $ y . de la columna Precio en el CSV
        time.sleep(1)
        df = pd.DataFrame(resultados)
        time.sleep(1)
        df.drop_duplicates(inplace=True)
        df['precio'] = df['precio'].replace({'\$': '', '\.': ''}, regex=True)
        df['precio'] = pd.to_numeric(df['precio'], errors='coerce')
        df['fecha'] = datetime.now().date()  # Añadir columna con el día actual
        df["orden_original"] = df.index.astype(int)
        df["fx_insert"] = datetime.now()
        time.sleep(1.5)
        logger.info("Símbolos de dólar y puntos eliminados de los precios.")
        
        df.to_sql(db_table, engine, if_exists="append", index=False)
        
        logging.info("Resultados guardados en la base de datos")
        
        context.close()
        browser.close()
        playwright.stop()

    except Exception as e:
        logger.error(f"Error en el proceso principal: {str(e)}")
        raise

if __name__ == '__main__':
    main()
