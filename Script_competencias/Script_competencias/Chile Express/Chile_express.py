import time
from playwright.sync_api import Playwright, sync_playwright, expect
import random
import os
import logging
import csv
import pandas as pd
from datetime import datetime
import os
from sqlalchemy import create_engine

db_user = "usr_postbi"
db_password = ""
db_host = "10.200.40.10"  # Ejemplo: 'localhost' o '127.0.0.1'
db_port = "5432"  # Puerto por defecto de PostgreSQL
db_name = "DWHP_WEBSCRAP"
db_table = "ft_precios_compe"

engine = create_engine(f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

log_file_path = os.path.join(os.path.dirname(__file__), "logs_chile_express.log")
# Configurar el logger
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

COMBINACIONES_FILE = os.path.join(os.path.dirname(__file__),'combinaciones_origen_destino_chile_express.csv')

def load_combinaciones():
    combinaciones = []
    with open(COMBINACIONES_FILE, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        next(reader)  # Saltar la cabecera
        for row in reader:
            combinaciones.append((row[0], row[1]))
    return combinaciones

def scrape_chilexpress():
    try:
        with sync_playwright() as p:
            
            # Iniciar el navegador
            browser =p.chromium.launch(headless=True)  # Cambiar a True si no necesitas ver el navegador
            context =browser.new_context(viewport={"width": 1920, "height": 1080})  # Vista amplia
            page =context.new_page()
            resultados=[]
            # Navegar a la página
            url = "https://personas.chilexpress.cl/cotizar/encomienda"
            page.goto(url)
            
            # Aplicar configuraciones iniciales
            aplicar_configuraciones_iniciales(page)

            # Intentar cerrar el anuncio emergente
            page.evaluate("""
                const overlays = document.querySelectorAll('div[id*="overlay"], iframe');
                overlays.forEach(el => el.remove());
            """)
            logging.info("Anuncio eliminado o no aparecio.")

            # Cargar combinaciones de origen y destino desde el CSV
            logging.info("Cargando combinaciones desde 'combinaciones_origen_destino_chile_express.csv'.")
            combinaciones = load_combinaciones()

            # Iterar sobre las combinaciones de origen y destino
            iterar_combinaciones(page, combinaciones, resultados)
            time.sleep(1.5)
            # Eliminar filas duplicadas del CSV
            logging.info("Eliminando filas duplicadas del dataframe.")
            df = pd.DataFrame(resultados)
            df.drop_duplicates(inplace=True)
            logging.info("Filas duplicadas eliminadas.")


            # Eliminar los símbolos de dólar y puntos de los precios
            logging.info("Eliminando símbolos de dólar y puntos de los precios en el archivo CSV.")
            df['precio'] = df['precio'].replace({'\$': '', '\.': ''}, regex=True)
            logging.info("Símbolos de dólar y puntos eliminados de los precios.")

            df['peso'] = pd.to_numeric(df['peso'], errors='coerce')
            df['alto'] = pd.to_numeric(df['alto'], errors='coerce')
            df['ancho'] = pd.to_numeric(df['ancho'], errors='coerce')
            df['largo'] = pd.to_numeric(df['largo'], errors='coerce')
            df['precio'] = pd.to_numeric(df['precio'], errors='coerce')
            df["orden_original"] = df.index.astype(int)
            df["fx_insert"] = datetime.now()

            time.sleep(2)
            df.to_sql(db_table, engine, if_exists="append", index=False)


            # Cerrar el navegador
            context.close()
            browser.close()

    except Exception as e:
        logging.error(f"Error en el scraping: {e}")

def aplicar_configuraciones_iniciales(page):
    """Aplica configuraciones iniciales como zoom y cierre de anuncios."""
    try:
        # Reducir zoom al 50%
        page.evaluate("document.body.style.zoom = '0.6'")
        time.sleep(random.uniform(1.6, 2.4))

    except Exception as e:
        logging.error("Error al aplicar configuraciones iniciales:", e)

def cerrar_menu(page):
    """Cierra el menú de autocompletado activo."""
    try:
        page.keyboard.press("Escape")
        time.sleep(1)
    except Exception as e:
        logging.error(f"Error al cerrar el menu: {e}")


def cerrar_overlay(page):
    """Cierra el overlay que está bloqueando el elemento."""
    try:
        logging.info("Cerrando overlay si está presente.")
        page.evaluate("""
            const overlay = document.querySelector('#hs-interactives-modal-overlay');
            if (overlay) {
                overlay.remove();
            }
        """)
        logging.info("Overlay cerrado.")
    except Exception as e:
        logging.error(f"Error al cerrar el overlay: {e}")

def select_origen_destino(page, origen, destino):
    """Selecciona el origen y destino en la página."""
    try:

        cerrar_overlay(page)
        # Seleccionar origen
        logging.info(f"Seleccionando origen: {origen}")
        page.click('#origen')
        page.fill('#origen', origen)
        time.sleep(1)
        cerrar_menu(page)

        # Seleccionar destino
        logging.info(f"Seleccionando destino: {destino}")
        page.click('[placeholder="Destino"]')
        page.fill('[placeholder="Destino"]', destino)
        time.sleep(1)
        cerrar_menu(page)

        logging.info(f"Seleccion completada: Origen = {origen}, Destino = {destino}")
        return True

    except Exception as e:
        logging.error(f"Error al seleccionar Origen ({origen}) o Destino ({destino}): {e}")
        return False

def iterar_combinaciones(page, combinaciones, resultados):
    """Itera a través de todas las combinaciones de origen y destino con reinicios completos."""
    pesos = [3, 6, 15]
    peso_inicial = 0.5
    alto = 10
    ancho = 10
    largo = 10
    max_reinicios = 15  # Máximo de reinicios por combinación

    combinaciones_extendido = [
        ("SANTIAGO CENTRO", "ANTOFAGASTA"),
        ("SANTIAGO CENTRO", "PUNTA ARENAS"),
        ("SANTIAGO CENTRO", "ARICA"),
        ("SANTIAGO CENTRO", "COYHAIQUE"),
        ("SANTIAGO CENTRO", "IQUIQUE")
    ]

    for origen, destino in combinaciones:
        reinicios = 0
        exito = False
        bandera=True
        while reinicios <= max_reinicios and not exito:
            try:
                logging.info(f"Procesando {origen}-{destino} (Reinicio {reinicios + 1}/{max_reinicios + 1})")
                
                # Reinicio completo: recargar página y rellenar datos
                page.reload()
                time.sleep(random.uniform(1.0, 2.0))  # Esperar después de recargar
                # Configuración inicial
                aplicar_configuraciones_iniciales(page)
                select_origen_destino(page, origen, destino)
                if not select_origen_destino: 
                    bandera=False # Por si falla la seleccion del origen o destino , por alguna mala carga de la página
                click_encomienda(page)
                fill_envio_protegido(page)
                select_medidas_personalizadas(page, largo, alto, ancho)
                time.sleep(random.uniform(0.2, 0.4))

                # Proceso principal
                for peso in [peso_inicial] + pesos:
                    try:
                        if peso != peso_inicial:
                            clear_peso(page)
                            time.sleep(random.uniform(0.2, 0.3))

                        fill_peso(page, peso)
                        time.sleep(random.uniform(0.5, 1.2))

                        # Scrapear servicios
                        servicios = scrape_servicio(page)

                        if not servicios:
                            logging.warning(f"No se encontraron servicios para peso {peso}")
                            exito =False
                            raise Exception("No se encontraron servicios")  # Forzar reinicio
                        

                        # Guardar resultados
                        tipo_requerido = "EXTENDIDO" if (origen, destino) in combinaciones_extendido else "EXPRESS"
                        for servicio in servicios:
                            if servicio["type"] == tipo_requerido:
                                resultados.append({
                                    "rut": "96.756.430-3",
                                    "origen": origen,
                                    "destino": destino,
                                    "ancho": ancho,
                                    "largo": largo,
                                    "alto": alto,
                                    "peso": peso,
                                    "precio": servicio["price"],
                                    "fecha": datetime.now().date()
                                })
                                exito = True  # Marcar como exitoso si al menos un servicio válido

                    except Exception as e:
                        logging.error(f"Error con peso {peso}: {str(e)}")
                        exito = False
                        raise  # Forzar reinicio completo

                if exito and bandera:
                    break  # Salir del bucle si tuvo éxito
                else:
                    reinicios+=1
                    bandera=True
            except Exception as e:
                logging.error(f"Error en la combinación {origen}-{destino}: {str(e)}")
                reinicios += 1
                if reinicios <= max_reinicios:
                    logging.info(f"Reiniciando proceso para {origen}-{destino}...")
                    time.sleep(random.uniform(2.0, 3.0))  # Esperar antes de reiniciar
                    bandera=True
                else:
                    logging.error(f"Fallo definitivo para {origen}-{destino} después de {max_reinicios} reinicios")

def click_encomienda(page):
    """Hace clic en el botón 'Encomienda'."""
    try:
        logging.info("Clic en 'Encomienda'")
        page.locator(".card > .px-3 > .row > div").first.click()
        logging.info("Clic en 'Encomienda' realizado.")
    except Exception as e:
        logging.error(f"Error al hacer clic en 'Encomienda': {e}")

def fill_envio_protegido(page):
    """Llena el valor declarado y selecciona el tipo de artículo."""
    try:
        logging.info("Llenando el valor declarado con '5000'")
        page.locator("#amount").click()
        page.locator("#amount").fill("5000")
        logging.info("Seleccionando tipo de artículo: 'ARTICULOS PERSONALES'")
        page.locator("select").select_option("1")  # Seleccionar "ARTÍCULOS PERSONALES"
        logging.info("Tipo de articulo seleccionado.")
        time.sleep(1)
    except Exception as e:
        logging.error(f"Error al llenar Envio Protegido: {e}")

def select_medidas_personalizadas(page, largo, alto, ancho):
    """Selecciona 'Medidas personalizadas' y llena las dimensiones con los valores proporcionados."""
    try:
        logging.info("Forzando visibilidad de la seccion 'Dimensiones de tu envio'.")

        # Forzar la visibilidad de la sección de dimensiones y botones
        page.evaluate("""
            const forceVisible = (selector) => {
                const element = document.querySelector(selector);
                if (element) {
                    element.style.display = 'block';
                    element.style.visibility = 'visible';
                    element.style.position = 'relative';
                    element.style.height = 'auto';
                    element.style.overflow = 'visible';
                }
            };

            // Forzar visibilidad de los botones de medidas
            forceVisible('button[aria-label="Medidas personalizadas"]');
            forceVisible('button[aria-label="Medidas estándar"]');

            // Forzar visibilidad de los campos de dimensiones
            ['height', 'width', 'length'].forEach(name => {
                const field = document.querySelector(`input[formcontrolname="${name}"]`);
                if (field) {
                    field.style.display = 'block';
                    field.style.visibility = 'visible';
                    field.style.position = 'relative';
                }
            });
        """)
        time.sleep(random.uniform(1.3, 1.9))

        # Detectar si existe el botón de 'Medidas estándar'
        medidas_estandar_button = page.query_selector('button[aria-label="Medidas estándar"]')
        if medidas_estandar_button:
            logging.info("'Medidas estándar' detectado. Seleccionando 'Medidas personalizadas'.")
            medidas_personalizadas_button = page.query_selector('button[aria-label="Medidas personalizadas"]')
            if (medidas_personalizadas_button):
                medidas_personalizadas_button.click()
                logging.info("'Medidas personalizadas' seleccionado correctamente.")
        else:
            logging.info("Solo está disponible 'Medidas personalizadas'. Procediendo directamente a llenarlas.")
        time.sleep(random.uniform(0.2, 0.4))
        # Hacer scroll dinámico a los campos de dimensiones
        logging.info("Haciendo scroll a los campos de dimensiones.")
        page.evaluate("""
            const scrollToFields = () => {
                ['height', 'width', 'length'].forEach(name => {
                    const field = document.querySelector(`input[formcontrolname="${name}"]`);
                    if (field) {
                        field.scrollIntoView({behavior: 'smooth', block: 'center'});
                    }
                });
            };
            scrollToFields();
        """)
        time.sleep(1)

        # Llenar los campos de dimensiones directamente
        logging.info("Llenando las dimensiones.")
        page.evaluate(f"""
            const fillDimensions = () => {{
                const dimensions = {{
                    height: '{ancho}',
                    width: '{alto}',
                    length: '{largo}'
                }};
                ['height', 'width', 'length'].forEach(name => {{
                    const field = document.querySelector(`input[formcontrolname="${{name}}"]`);
                    if (field) {{
                        field.value = dimensions[name];
                        const event = new Event('input', {{ bubbles: true }});
                        field.dispatchEvent(event);
                    }}
                }});
            }};
            fillDimensions();
        """)
        logging.info("Dimensiones llenadas correctamente.")

    except Exception as e:
        logging.error(f"Error al seleccionar 'Medidas personalizadas' o llenar las dimensiones: {e}")

def clear_peso(page):
    """Limpia el campo de peso."""
    try:
        logging.info("Limpiando el campo de peso.")
        page.evaluate("""
            const clearWeight = () => {
                const weightField = document.querySelector('input[formcontrolname="weight"][pe="number"]');
                if (weightField) {
                    weightField.value = '';
                    const event = new Event('input', { bubbles: true });
                    weightField.dispatchEvent(event);
                }
            };
            clearWeight();
        """)
        logging.info("Campo de peso limpiado correctamente.")
    except Exception as e:
        logging.error(f"Error al limpiar el campo de peso: {e}")

def fill_peso(page, peso):
    """Llena el campo de peso con el valor proporcionado."""
    try:
        logging.info("Llenando el peso.")
        page.evaluate(f"""
            const fillWeight = () => {{
                const weightField = document.querySelector('input[formcontrolname="weight"][pe="number"]');
                if (weightField) {{
                    weightField.value = '{peso}';
                    const event = new Event('input', {{ bubbles: true }});
                    weightField.dispatchEvent(event);
                }}
            }};
            fillWeight();
        """)
        logging.info("Peso llenado correctamente.")
    except Exception as e:
        logging.error(f"Error al llenar el peso: {e}")

def scrape_servicio(page):
    """Scrapea todos los servicios disponibles desplazándose hacia la sección y extrayendo datos."""
    try:
        logging.info("Forzando visibilidad de la sección 'Servicio'.")

        # Forzar la visibilidad del contenedor de servicios
        page.evaluate("""
            const serviceContainer = document.querySelector('app-bloque-servicios');
            if (serviceContainer) {
                serviceContainer.style.display = 'block';
                serviceContainer.style.visibility = 'visible';
                serviceContainer.style.position = 'relative';
                serviceContainer.style.height = 'auto';
                serviceContainer.style.overflow = 'visible';
            }
        """)
        time.sleep(random.uniform(0.7, 1.5))

        # Hacer scroll al contenedor de servicios
        logging.info("Haciendo scroll al contenedor de servicios.")
        page.evaluate("""
            const serviceContainer = document.querySelector('app-bloque-servicios');
            if (serviceContainer) {
                serviceContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        """)
        time.sleep(random.uniform(1.6, 2.4))  # Esperar que el scroll y la carga se completen

        # Verificar si los servicios están visibles
        logging.info("Verificando visibilidad de los servicios.")
        is_visible = page.evaluate("""
            (() => {
                const serviceContainer = document.querySelector('app-bloque-servicios');
                if (serviceContainer) {
                    const rect = serviceContainer.getBoundingClientRect();
                    return rect.top < window.innerHeight && rect.bottom > 0;
                }
                return false;
            })()
        """)

        if not is_visible:
            raise Exception("No se pudo encontrar la seccion de servicios.")

        # Esperar a que los servicios estén disponibles
        logging.info("Esperando a que los servicios estén disponibles...")
        page.wait_for_selector('label.card', timeout=10000)

        # Extraer información de todos los servicios
        logging.info("Extrayendo todos los servicios disponibles...")
        servicios = page.evaluate("""
            (() => {
                const services = [];
                document.querySelectorAll('label.card').forEach(service => {
                    const typeElement = service.querySelector('div.h5, div.h6 b'); // Tipo de servicio
                    const priceElement = service.querySelector('div.h5.mb-0'); // Precio del servicio

                    if (typeElement && priceElement) {
                        services.push({
                            type: typeElement.innerText.trim(),
                            price: priceElement.innerText.trim()
                        });
                    }
                });
                return services;
            })()
        """)

        if servicios and len(servicios) > 0:
            logging.info(f"Servicios encontrados: {servicios}")
        else:
            logging.warning("No se encontraron servicios disponibles.")
        return servicios

    except Exception as e:
        logging.error(f"Error al scrapear servicios: {e}")
        return []
# Ejecutar la función de scraping
scrape_chilexpress()
