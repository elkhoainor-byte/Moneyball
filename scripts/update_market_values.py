import pandas as pd
import requests
import io
from rapidfuzz import process, fuzz

print("Descargando datos de Transfermarkt...")

url = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/players.csv.gz"
response = requests.get(url)
tm = pd.read_csv(io.BytesIO(response.content), compression="gzip")

tm = tm[["name", "market_value_in_eur"]].copy()
tm = tm.dropna(subset=["name", "market_value_in_eur"])
tm["name_clean"] = tm["name"].str.lower().str.strip()

print(f"Jugadores de Transfermarkt cargados: {len(tm)}")

print("Leyendo datos.csv de FBRef...")

# Como el nuevo archivo usa coma
raw = pd.read_csv(
    "datos.csv",
    header=None,
    sep=",",
    engine="python",
    on_bad_lines="skip",
    encoding="utf-8",
    encoding_errors="replace"
)

print(f"Filas leídas: {len(raw)}")
print("Primeras filas:")
print(raw.head(6))

# Buscar la fila de cabecera
header_row_index = None
for i in range(min(15, len(raw))):
    row_str = " ".join(raw.iloc[i].astype(str).str.lower().tolist())
    if "player" in row_str and "nation" in row_str:
        header_row_index = i
        break

if header_row_index is None:
    raise Exception("No se encontró la fila de cabecera")

print(f"Cabecera encontrada en la fila: {header_row_index}")

headers = raw.iloc[header_row_index].astype(str).str.replace("\n", " ").str.strip().tolist()
fbref = raw.iloc[header_row_index + 1:].copy()
fbref.columns = headers

# Limpiar nombres de columnas
fbref.columns = [str(c).replace("\n", " ").strip() for c in fbref.columns]
fbref = fbref.loc[:, ~fbref.columns.duplicated()]

print("Columnas detectadas:", list(fbref.columns)[:12])

# Asegurarnos de que existe la columna Player
if "Player" not in fbref.columns:
    # A veces viene como primera columna con nombre raro
    possible = [c for c in fbref.columns if "player" in str(c).lower()]
    if possible:
        fbref = fbref.rename(columns={possible[0]: "Player"})
    else:
        raise Exception(f"No se encontró columna Player. Columnas: {list(fbref.columns)}")

fbref = fbref.dropna(subset=["Player"])
fbref = fbref[fbref["Player"].astype(str).str.lower().str.strip() != "player"]

print(f"Jugadores de FBRef cargados: {len(fbref)}")
print("Ejemplos de nombres:")
print(fbref["Player"].head(10).tolist())

# Matching
fbref["name_clean"] = fbref["Player"].astype(str).str.lower().str.strip()

def find_best_match(name, choices, threshold=85):
    if not isinstance(name, str) or name.lower() in ["", "nan", "none"]:
        return None
    match = process.extractOne(name, choices, scorer=fuzz.token_sort_ratio)
    if match and match[1] >= threshold:
        return match[0]
    return None

print("Haciendo matching de nombres...")

choices = tm["name_clean"].tolist()
fbref["matched_name"] = fbref["name_clean"].apply(lambda x: find_best_match(x, choices))

merged = fbref.merge(
    tm[["name_clean", "market_value_in_eur"]],
    left_on="matched_name",
    right_on="name_clean",
    how="left"
)

cols_to_drop = [c for c in merged.columns if "name_clean" in str(c) or c == "matched_name"]
merged = merged.drop(columns=cols_to_drop, errors="ignore")
merged = merged.rename(columns={"market_value_in_eur": "MarketValue"})

merged.to_csv("datos_con_valor.csv", index=False, sep=",", encoding="utf-8-sig")

matched = merged["MarketValue"].notna().sum()
print(f"¡Listo! Se han emparejado {matched} de {len(merged)} jugadores.")
print("Archivo generado: datos_con_valor.csv")
