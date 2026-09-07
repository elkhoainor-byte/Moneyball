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

# Intentamos varias codificaciones de forma más tolerante
encodings_to_try = ["utf-8", "utf-8-sig", "latin1", "cp1252", "iso-8859-1"]

raw = None
used_encoding = None

for enc in encodings_to_try:
    try:
        print(f"Probando encoding: {enc}")
        temp = pd.read_csv(
            "datos.csv",
            header=None,
            sep=";",
            engine="python",
            on_bad_lines="skip",
            encoding=enc,
            encoding_errors="replace"   # Reemplaza caracteres problemáticos en vez de fallar
        )
        if len(temp.columns) > 3:
            raw = temp
            used_encoding = enc
            print(f"Encoding aceptado: {enc}")
            break
    except Exception as e:
        print(f"Falló con {enc}: {e}")
        continue

if raw is None:
    # Último intento muy agresivo
    print("Último intento con latin1 + replace...")
    raw = pd.read_csv(
        "datos.csv",
        header=None,
        sep=";",
        engine="python",
        on_bad_lines="skip",
        encoding="latin1",
        encoding_errors="replace"
    )
    used_encoding = "latin1 (forzado)"

print(f"Usando encoding: {used_encoding}")
print(f"Filas leídas: {len(raw)}")
print("Muestra de las primeras filas:")
print(raw.head(6))

# Buscar cabecera
header_row_index = None
for i in range(min(25, len(raw))):
    row_as_str = raw.iloc[i].astype(str).str.lower().str.strip()
    if row_as_str.str.contains("player").any():
        header_row_index = i
        break

if header_row_index is None:
    raise Exception("No se encontró la fila de cabecera con 'Player'")

print(f"Cabecera encontrada en la fila: {header_row_index}")

headers = raw.iloc[header_row_index].astype(str).str.replace("\n", " ").str.strip().tolist()
fbref = raw.iloc[header_row_index + 1:].copy()
fbref.columns = headers
fbref.columns = [str(c).replace("\n", " ").strip() for c in fbref.columns]
fbref = fbref.loc[:, ~fbref.columns.duplicated()]

fbref = fbref.dropna(subset=["Player"])
fbref = fbref[fbref["Player"].astype(str).str.lower().str.strip() != "player"]

print(f"Jugadores de FBRef cargados: {len(fbref)}")
print("Ejemplos de nombres:")
print(fbref["Player"].head(12).tolist())

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

# Guardar en UTF-8
merged.to_csv("datos_con_valor.csv", index=False, sep=";", encoding="utf-8-sig")

matched = merged["MarketValue"].notna().sum()
print(f"¡Listo! Se han emparejado {matched} de {len(merged)} jugadores.")
print("Archivo generado: datos_con_valor.csv")
