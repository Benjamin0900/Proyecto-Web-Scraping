import pandas as pd
from playwright.sync_api import Playwright, sync_playwright, expect ,Page
import time
from sqlalchemy import create_engine
import csv
import os
import logging
from datetime import datetime

db_user = "usr_postbi"
db_password = ""
db_host = "10.200.40.10"  # Ejemplo: 'localhost' o '127.0.0.1'
db_port = "5432"  # Puerto por defecto de PostgreSQL
db_name = "DWHP_WEBSCRAP"
db_table = "ft_precios_compe"

engine = create_engine(f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

log_file_path = os.path.join(os.path.dirname(__file__), "logs_starken.log")
# Configurar el logger
logging.basicConfig(filename=log_file_path, level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_starken(alto, largo, ancho, peso, valor_declarado):
    with sync_playwright() as p:
        

        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        url = "https://www.starken.cl/cotizador"
        page.goto(url, timeout=60000)
        logging.info(f"------------------------------------------------------------------")
        logging.info(f"Abriendo la página: {url}")

        # Leer combinaciones de origen y destino desde el archivo CSV
        combinaciones_file = os.path.join(os.path.dirname(__file__),"combinaciones_origen_destino_starken.csv")
        combinaciones = []
        try:
            with open(combinaciones_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    combinaciones.append(row)
            logging.info(f"Combinaciones cargadas desde el archivo: {len(combinaciones)}")
        except FileNotFoundError:
            logging.error(f"No se encontró el archivo {combinaciones_file}")
            return


        first_combination = True
        time.sleep(3.5)  # Pausa para asegurarnos de que la página se cargue completamente

        logging.info("Llenando valores de dimensiones y peso...")
        fill_fields(page, {
            "#altoForm": alto,
            "#largoForm": largo,
            "#anchoForm": ancho,
            "#pesoForm": peso,
            "#valorDeclarado": valor_declarado,
        })

        resultados=[]

        for combinacion in combinaciones:
            origen = combinacion["Origen"]
            destino = combinacion["Destino"]

            try:
                # Seleccionar el origen
                logging.info(f"Seleccionando origen: {origen}...")
                select_option(page, "#origenForm", origen, "origen", nth_match=0)
                logging.info(f"Origen seleccionado: {origen}")

                # Seleccionar el destino
                logging.info(f"Seleccionando destino: {destino}...")
                nth_match = 1 if origen == destino else 0
                select_option(page, "#destinoForm", destino, "destino", nth_match=nth_match)
                logging.info(f"Destino seleccionado: {destino}")
            except Exception as e:
                logging.error(f"Error seleccionando origen/destino {origen} -> {destino}: {e}")
                continue
            time.sleep(1)
            # Iterar sobre los valores de peso
            for peso_actual in [0.5, 3, 6, 15]:
                try:
                    # Cambiar el valor del peso
                    logging.info(f"Actualizando peso a {peso_actual}...")
                    fill_fields(page, {"#pesoForm": str(peso_actual)})
                    time.sleep(1)
                    # Click en Cotizar o Volver a Cotizar
                    if first_combination and peso_actual == 0.5:
                        logging.info("Clickeando 'Cotizar'...")
                        click_button(page, "#Bcotizar")
                        time.sleep(1.5)
                        ensure_popup_closed(page)
                        first_combination = False
                    else:
                        logging.info("Clickeando 'Volver a cotizar'...")
                        click_button(page, "#Bvolvercotizar")
                        time.sleep(1.5)
                        ensure_popup_closed(page)

                    # Esperar a que carguen los precios
                    logging.info("Esperando precios...")
                    try:
                        time.sleep(1.2)
                        page.wait_for_selector(".cardTarifaDisponible")
                        
                    except Exception:
                        logging.warning(f"Precios no disponibles para {origen} -> {destino} con peso {peso_actual}")
                        #await page.screenshot(path=f"screenshot_{origen}_{destino}_peso_{peso_actual}.png")
                        retry_count = 0
                        max_retries = 3
                        while retry_count < max_retries:
                            try:
                                page.reload()
                                time.sleep(10)
                                fill_fields(page, {
                                    "#altoForm": alto,
                                    "#largoForm": largo,
                                    "#anchoForm": ancho,
                                    "#pesoForm": peso_actual,
                                    "#valorDeclarado": valor_declarado,
                                })
                                select_option(page, "#origenForm", origen, "origen", nth_match=0)
                                time.sleep(1)
                                select_option(page, "#destinoForm", destino, "destino", nth_match=nth_match)
                                logging.info("Clickeando 'Cotizar'...")
                                click_button(page, "#Bcotizar")
                                time.sleep(1.5)
                                ensure_popup_closed(page)
                                time.sleep(2)
                                logging.info("Esperando precios...")
                                page.wait_for_selector(".cardTarifaDisponible")
                                break  # Salir del bucle si todo va bien
                            except Exception as e:
                                retry_count += 1
                                logging.error(f"Error al reiniciar el proceso para {origen} -> {destino} con peso {peso_actual}: {e}")
                                if retry_count >= max_retries:
                                    logging.error(f"Maximos reintentos alcanzados para {origen} -> {destino} con peso {peso_actual}")
                                    break
                        
                        continue

                    # Extraer precios
                    precios_sucursal, precios_domicilio, precios_aereo = extract_prices(page)

                    
                    resultados.append({
                        "rut": "96.794.750-4",
                        "origen": origen,
                        "destino": destino,
                        "alto": alto,
                        "ancho": ancho,
                        "largo": largo,
                        "peso": peso_actual,
                        "sucursal": precios_sucursal,
                        "domicilio": precios_domicilio,
                        "aereo_a_domicilio": precios_aereo,
                        "fecha": datetime.now().date()
                    })
                    time.sleep(0.5)#para evitar popups

                except Exception as e:
                    logging.error(f"Error al procesar {origen} -> {destino} con peso {peso_actual}: {e}")
                    continue
        time.sleep(1.5)
        df = pd.DataFrame(resultados)
        df['peso'] = pd.to_numeric(df['peso'], errors='coerce')
        df['alto'] = pd.to_numeric(df['alto'], errors='coerce')
        df['ancho'] = pd.to_numeric(df['ancho'], errors='coerce')
        df['largo'] = pd.to_numeric(df['largo'], errors='coerce')
        df['sucursal'] = pd.to_numeric(df['sucursal'], errors='coerce')
        df['domicilio'] = pd.to_numeric(df['domicilio'], errors='coerce')
        df['aereo_a_domicilio'] = pd.to_numeric(df['aereo_a_domicilio'], errors='coerce')
        df["orden_original"] = df.index.astype(int)
        df["fx_insert"] = datetime.now()
        
        time.sleep(3)
        df.to_sql(db_table, engine, if_exists="append", index=False)

        logging.info("Scraping completado. Resultados guardados en la base de datos")
        time.sleep(4)


        context.close()
        browser.close()
        

def ensure_popup_closed(page):
    try:
        # Selector para el popup y su botón "Aceptar"
        popup_selector = ".ant-modal.modal-no-cotiza"
        accept_button_selector = ".ant-modal.modal-no-cotiza button.ant-btn-default:has-text('Aceptar')"

        # Esperar a que el popup esté presente y visible
        popup = page.locator(popup_selector)
        try:
            popup.wait_for(state="visible", timeout=5000)
        except Exception:
            logging.info("No se detecto popup.")
            return

        if popup.is_visible():
            logging.info("Popup detectado. Cerrándolo...")

            # Intentar hacer clic en el botón "Aceptar"
            time.sleep(4)
            accept_button = page.locator(accept_button_selector)
            try:
                accept_button.wait_for(state="visible", timeout=10000)
                accept_button.click()
                logging.info("Boton 'Aceptar' clickeado exitosamente.")
                logging.info("Clickeando 'Volver a cotizar luego del anuncio'...")
                time.sleep(3)
                click_button(page, "#Bvolvercotizar")
            except Exception as e:
                logging.error(f"Error clickeando el boton 'Aceptar': {e}")

            # Esperar a que el popup desaparezca
            popup.wait_for(state="hidden", timeout=10000)
            logging.info("Popup cerrado exitosamente.")
        else:
            logging.info("No se detecto popup.")
    except Exception as e:
        logging.error(f"Error al cerrar el popup: {e}")

def fill_fields(page, fields):
    try:
        for selector, value in fields.items():
            logging.info(f"Llenando campo {selector} con valor {value}...")
            field = page.locator(selector)
            field.wait_for(state="visible", timeout=20000)  # Esperar a que el campo esté visible
            field.fill(value)
            time.sleep(1)  # Pausa breve para garantizar estabilidad
    except Exception as e:
        logging.error(f"Error llenando campos: {e}")
        raise

def click_button(page, button_selector):
    try:
        button = page.locator(button_selector)
        button.wait_for(state="visible", timeout=20000)
        if not button.is_enabled():
            raise Exception(f"Boton {button_selector} no esta habilitado.")
        button.click()
        logging.info(f"Boton {button_selector} clickeado exitosamente.")
    except Exception as e:
        logging.error(f"Error clickeando el boton {button_selector}: {e}")

def extract_prices(page: Page):
    try:
        precios_sucursal = "NaN"
        precios_domicilio = "NaN"
        precios_aereo = "NaN"

        time.sleep(1)  # Pausa para asegurarnos de que los precios se carguen
        # Intentar obtener el precio para envío a sucursal
        try:
            precios_sucursal_element = page.locator("#Bnormalsucursal .valor-card-tarifa").text_content()
            precios_sucursal = precios_sucursal_element.replace('$', '').replace('.', '').strip() if precios_sucursal_element else "NaN"
        except Exception:
            logging.warning("Envio a Sucursal no disponible")

        # Intentar obtener el precio para envío a domicilio
        try:
            precios_domicilio_element = page.locator("#Bnormaldomicilio .valor-card-tarifa").text_content()
            precios_domicilio = precios_domicilio_element.replace('$', '').replace('.', '').strip() if precios_domicilio_element else "NaN"
        except Exception:
            logging.warning("Envio a Domicilio no disponible")

        # Intentar obtener el precio para envío aéreo
        try:
            if page.locator("#Baereodomicilio").count() > 0:
                precios_aereo_element = page.locator("#Baereodomicilio .valor-card-tarifa").text_content()
                precios_aereo = precios_aereo_element.replace('$', '').replace('.', '').strip() if precios_aereo_element else "NaN"
            else:
                logging.info("Selector Baereodomicilio no disponible")
        except Exception:
            logging.warning("Envio aereo no disponible")

        return precios_sucursal, precios_domicilio, precios_aereo
    except Exception as e:
        logging.error(f"Error extrayendo precios: {e}")
        return "NaN", "NaN", "NaN"

def save_progress(file_path, row):
    with open(file_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

def select_option(page: Page, input_selector: str, value: str, context: str, nth_match: int = 0):
    try:
        logging.info(f"Intentando seleccionar la opción '{value}' para {context}...")

        # Limpiar el campo de selección si hay una opción seleccionada previamente
        clear_button_selector = f"{input_selector} + .ant-select-clear"
        if page.locator(clear_button_selector).is_visible():
            page.click(clear_button_selector)
            time.sleep(1)  # Pausa para asegurarnos de que el campo se limpia

        # Escribir el valor en el campo de búsqueda
        page.fill(input_selector, value)
        time.sleep(1)  # Pausa para asegurarnos de que el valor se escribe

        # Buscar todas las coincidencias del menú desplegable
        option_selector = f".ant-select-item-option[title='{value}']"
        options = page.locator(option_selector).all()

        # Verificar cuántas opciones coinciden con el selector
        if len(options) > nth_match:
            logging.info(f"Se encontraron {len(options)} opciones para '{value}'. Seleccionando la opción #{nth_match + 1}.")
            target_option = options[nth_match]
            if target_option.is_visible():
                target_option.click()  # Seleccionar la opción según el índice
            else:
                raise ValueError(f"La opción #{nth_match + 1} para '{value}' no está visible.")
        else:
            raise ValueError(f"No se encontró la opción #{nth_match + 1} para '{value}'. Opciones disponibles: {len(options)}.")

        time.sleep(1)  # Pausa para asegurarnos de que la opción se selecciona
        logging.info(f"Opción '{value}' seleccionada correctamente para {context}.")
    except Exception as e:
        logging.error(f"Error al seleccionar la opción '{value}' para {context}: {e}")
        raise



# Ejecutar el script con parámetros de dimensiones y peso
alto = "10"
largo = "10"
ancho = "10"
peso = "1"
valor_declarado = "5000"
scrape_starken(alto, largo, ancho, peso, valor_declarado)
