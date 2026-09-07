import pandas as pd
import requests
import io
from rapidfuzz import process, fuzz

print("Descargando datos de Transfermarkt...")

# Descargamos el dataset público de jugadores de Transfermarkt
url = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/players.csv.gz"
response = requests.get(url)
tm = pd.read_csv(io.BytesIO(response.content), compression="gzip")

# Nos quedamos solo con las columnas que necesitamos
tm = tm[["name", "market_value_in_eur", "current_club_name"]].copy()
tm = tm.dropna(subset=["name", "market_value_in_eur"])
tm["name_clean"] = tm["name"].str.lower().str.strip()

print(f"Jugadores de Transfermarkt cargados: {len(tm)}")

# Cargamos tu CSV actual
fbref = pd.read_csv("datos.csv")
print(f"Jugadores de FBRef cargados: {len(fbref)}")

# Limpiamos el nombre en FBRef
fbref["name_clean"] = fbref["Player"].str.lower().str.strip()

# Hacemos matching por nombre (fuzzy matching)
def find_best_match(name, choices, threshold=85):
    match = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= threshold:
        return match[0]
    return None

print("Haciendo matching de nombres (esto puede tardar un poco)...")

choices = tm["name_clean"].tolist()
fbref["matched_name"] = fbref["name_clean"].apply(lambda x: find_best_match(x, choices))

# Unimos los valores de mercado
merged = fbref.merge(
    tm[["name_clean", "market_value_in_eur"]],
    left_on="matched_name",
    right_on="name_clean",
    how="left"
)

# Limpiamos columnas temporales
merged = merged.drop(columns=["name_clean", "matched_name", "name_clean_y"], errors="ignore")
merged = merged.rename(columns={"market_value_in_eur": "MarketValue"})

# Guardamos el nuevo archivo
merged.to_csv("datos_con_valor.csv", index=False)

matched = merged["MarketValue"].notna().sum()
print(f"¡Listo! Se han emparejado {matched} de {len(merged)} jugadores.")
print("Archivo generado: datos_con_valor.csv")
