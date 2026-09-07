import pandas as pd
import requests
import io
from rapidfuzz import process, fuzz

print("Descargando datos de Transfermarkt...")

# Descargamos el dataset público de jugadores de Transfermarkt
url = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/players.csv.gz"
response = requests.get(url)
tm = pd.read_csv(io.BytesIO(response.content), compression="gzip")

# Nos quedamos solo con las columnas necesarias
tm = tm[["name", "market_value_in_eur"]].copy()
tm = tm.dropna(subset=["name", "market_value_in_eur"])
tm["name_clean"] = tm["name"].str.lower().str.strip()

print(f"Jugadores de Transfermarkt cargados: {len(tm)}")

# ========== LEER EL CSV DE FBREF (con cabeceras multilinea) ==========
print("Leyendo datos.csv de FBRef...")

raw = pd.read_csv("datos.csv", header=None)

# Buscamos la fila que contiene "Player"
header_row_index = None
for i in range(min(15, len(raw))):
    row_values = raw.iloc[i].astype(str).str.lower().str.strip()
    if row_values.str.contains("player").any():
        header_row_index = i
        break

if header_row_index is None:
    raise Exception("No se encontró la fila de cabecera con 'Player'")

print(f"Cabecera encontrada en la fila: {header_row_index}")

# Usamos esa fila como cabecera
headers = raw.iloc[header_row_index].astype(str).str.strip().tolist()
fbref = raw.iloc[header_row_index + 1:].copy()
fbref.columns = headers

# Limpiamos nombres de columnas (quitamos saltos de línea etc.)
fbref.columns = [str(c).replace("\n", " ").strip() for c in fbref.columns]

# Eliminamos filas vacías o que no tengan Player
fbref = fbref.dropna(subset=["Player"])
fbref = fbref[fbref["Player"].astype(str).str.lower() != "player"]

print(f"Jugadores de FBRef cargados: {len(fbref)}")
print("Columnas detectadas:", list(fbref.columns)[:10])

# ========== MATCHING DE NOMBRES ==========
fbref["name_clean"] = fbref["Player"].astype(str).str.lower().str.strip()

def find_best_match(name, choices, threshold=85):
    if not name or name == "nan":
        return None
    match = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= threshold:
        return match[0]
    return None

print("Haciendo matching de nombres (puede tardar 1-2 minutos)...")

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
cols_to_drop = [c for c in merged.columns if c in ["name_clean_x", "name_clean_y", "matched_name", "name_clean"]]
merged = merged.drop(columns=cols_to_drop, errors="ignore")
merged = merged.rename(columns={"market_value_in_eur": "MarketValue"})

# Guardamos el nuevo archivo
merged.to_csv("datos_con_valor.csv", index=False)

matched = merged["MarketValue"].notna().sum()
print(f"¡Listo! Se han emparejado {matched} de {len(merged)} jugadores.")
print("Archivo generado: datos_con_valor.csv")
