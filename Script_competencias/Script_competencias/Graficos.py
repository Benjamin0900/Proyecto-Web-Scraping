import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# Definir la ruta del archivo
file_path = os.path.join(os.path.dirname(__file__), "Resultados", "entregable.xlsx")

# Cargar los datos desde el Excel
df = pd.read_excel(file_path, sheet_name="Ponderaciones domicilio", usecols="A:Q", nrows=6)

# Renombrar las columnas manualmente
df.columns = [
    "Ruta/DIM", "CCH_XS", "CCH_S", "CCH_M", "CCH_L",
    "Starken_XS", "Starken_S", "Starken_M", "Starken_L",
    "Blue_XS", "Blue_S", "Blue_M", "Blue_L",
    "CH_Express_XS", "CH_Express_S", "CH_Express_M", "CH_Express_L"
]

# Eliminar la primera fila (encabezado de tamaños repetido)
df = df.iloc[1:].reset_index(drop=True)

# Reemplazar "Sin Servicio" por NaN y convertir valores a números
df.replace("Sin Servicio", np.nan, inplace=True)
df.iloc[:, 1:] = df.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")

# Crear la carpeta "Resultados si no existe
output_folder = os.path.join(os.path.dirname(__file__), "Resultados")

# Definir tamaños y empresas
sizes = ["XS", "S", "M", "L"]
empresas = ["CCH", "Starken", "Blue", "CH_Express"]
colores = ["#FF5733", "#33FF57", "#3357FF", "#F4C300"]  # Colores personalizados para cada empresa

# Graficar precios comparativos en barras para cada ruta
for index, row in df.iterrows():
    ruta = row["Ruta/DIM"]
    
    plt.figure(figsize=(10, 5))
    
    x = np.arange(len(sizes))  # Posiciones en el eje X (tamaños)
    width = 0.2  # Ancho de las barras
    
    for i, empresa in enumerate(empresas):
        valores = [row[f"{empresa}_{size}"] for size in sizes]
        plt.bar(x + i * width, valores, width=width, label=empresa, color=colores[i])

    plt.xlabel("Tamaño del Paquete")
    plt.ylabel("Precio ($)")
    plt.title(f"Comparación de Precios a Domicilio - Ruta {ruta}")
    plt.xticks(x + width * (len(empresas) / 2), sizes)
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Guardar el gráfico en la carpeta "Gráficos"
    plt.savefig(os.path.join(output_folder, f"comparacion_precios_domicilio_{ruta}.png"), bbox_inches="tight")
    plt.close()

print("Gráficos guardados exitosamente en formato de barras por ruta (domicilio).")


#-------------------------------------------------------------------------------------------
#Seccion graficos sucursal
df_s= pd.read_excel(file_path, sheet_name="Ponderaciones sucursal", usecols="A:Q", nrows=6)
# Renombrar las columnas manualmente
df_s.columns = [
    "Ruta/DIM", "CCH_XS", "CCH_S", "CCH_M", "CCH_L",
    "Starken_XS", "Starken_S", "Starken_M", "Starken_L",
    "Blue_XS", "Blue_S", "Blue_M", "Blue_L",
    "CH_Express_XS", "CH_Express_S", "CH_Express_M", "CH_Express_L"
]

# Eliminar la primera fila (encabezado de tamaños repetido)
df_s = df_s.iloc[1:].reset_index(drop=True)

# Reemplazar "Sin Servicio" por NaN y convertir valores a números
df_s.replace("Sin Servicio", np.nan, inplace=True)
df_s.iloc[:, 1:] = df_s.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")


# Definir tamaños y empresas
sizes = ["XS", "S", "M", "L"]
empresas = ["CCH", "Starken", "Blue", "CH_Express"]
colores = ["#FF5733", "#33FF57", "#3357FF", "#F4C300"]  # Colores personalizados para cada empresa

# Graficar precios comparativos en barras para cada ruta
for index, row in df.iterrows():
    ruta = row["Ruta/DIM"]
    
    plt.figure(figsize=(10, 5))
    
    x = np.arange(len(sizes))  # Posiciones en el eje X (tamaños)
    width = 0.2  # Ancho de las barras
    
    for i, empresa in enumerate(empresas):
        valores = [row[f"{empresa}_{size}"] for size in sizes]
        plt.bar(x + i * width, valores, width=width, label=empresa, color=colores[i])

    plt.xlabel("Tamaño del Paquete")
    plt.ylabel("Precio ($)")
    plt.title(f"Comparación de Precios a sucursal- Ruta {ruta}")
    plt.xticks(x + width * (len(empresas) / 2), sizes)
    plt.legend()
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    # Guardar el gráfico en la carpeta "Gráficos"
    plt.savefig(os.path.join(output_folder, f"comparacion_precios_sucursal_{ruta}.png"), bbox_inches="tight")
    plt.close()

print("Gráficos guardados exitosamente en formato de barras por ruta (sucursal).")

#-------------------------------------------------------------------------------------------