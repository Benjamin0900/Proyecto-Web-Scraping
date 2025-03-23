import subprocess
import os

# Definir rutas de los scripts
scripts = [
    os.path.join("Blue Express", "blue_express.py"),
    os.path.join("Chile Express", "Chile_express.py"),
    os.path.join("Starken", "Starken.py"),
    os.path.join("Chile Express Emprendedores", "Chile_express_emprendedores.py"),
    os.path.join("Correos Chile", "Correos_chile.py"),
    os.path.join(os.path.dirname(__file__), "ETL_1.py"),
    os.path.join(os.path.dirname(__file__), "ETL_2.py"),
    os.path.join(os.path.dirname(__file__), "ETL_3.py"),
    os.path.join(os.path.dirname(__file__), "ETL_4.py"),
    os.path.join(os.path.dirname(__file__), "Graficos.py")
]

# Ejecutar cada script
for script in scripts:
    try:
        print(f"Ejecutando {script}...")
        subprocess.run(["python", script], check=True)
        print(f"{script} ejecutado correctamente.\n")
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar {script}: {e}\n")
    except FileNotFoundError:
        print(f"Archivo no encontrado: {script}\n")
