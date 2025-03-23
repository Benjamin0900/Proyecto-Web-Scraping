import os
from sqlalchemy import create_engine
import pandas as pd
from datetime import datetime
import time

csv_file = os.path.join(os.path.dirname(__file__), "precios_correos_chile.csv")
# Configuración de la conexión a PostgreSQL
db_user = "usr_postbi"
db_password = ""
db_host = "10.200.40.10"  # Ejemplo: 'localhost' o '127.0.0.1'
db_port = "5432"  # Puerto por defecto de PostgreSQL
db_name = "DWHP_WEBSCRAP"
db_table = "ft_precios_compe"

# Crear la conexión usando SQLAlchemy
engine = create_engine(f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}")

resultados_df=pd.read_csv(csv_file)
resultados_df['fecha'] = datetime.now().date()
resultados_df['rut'] = '60.503.000-9'
resultados_df["orden_original"] = resultados_df.index.astype(int)
resultados_df["fx_insert"] = datetime.now()
time.sleep(2)
resultados_df.to_sql(db_table, engine, if_exists="append", index=False)



