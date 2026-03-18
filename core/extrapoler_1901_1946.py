import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
input_file = BASE_DIR / "tables_esperance_vie_LU_1901_2025.csv"
output_file = BASE_DIR / "tables_esperance_vie_LU_1901_2025_extrapole.csv"

df = pd.read_csv(input_file, sep=";")

# On s'assure des bons types
df["annee_reference"] = df["annee_reference"].astype(int)
df["age"] = df["age"].astype(int)
df["esperance_vie_restante"] = (
    df["esperance_vie_restante"]
    .astype(str)
    .str.replace(",", ".", regex=False)
    .astype(float)
)

# On prend 1947 comme année de référence
ref_year = 1947
k = 0.15  # baisse d'espérance (en années) par année de calendrier

# On extrait les valeurs de 1947 par sexe et âge
ref_1947 = df[df["annee_reference"] == ref_year].copy()

# Clé (sexe, age) -> espérance 1947
ref_map = {
    (row["sexe"], row["age"]): row["esperance_vie_restante"]
    for _, row in ref_1947.iterrows()
}

# On va modifier uniquement les lignes 1901–1946
mask_past = df["annee_reference"].between(1901, 1946)

def ajuster_ev(row):
    year = row["annee_reference"]
    sexe = row["sexe"]
    age = row["age"]

    base = ref_map.get((sexe, age))
    if base is None:
        # si on n'a pas de valeur ref pour cet âge/sexe, on garde la valeur existante
        return row["esperance_vie_restante"]

    delta_years = ref_year - year  # ex: 1947 - 1901 = 46
    ev = base - k * delta_years
    return max(ev, 0.0)  # jamais en dessous de 0

df.loc[mask_past, "esperance_vie_restante"] = df[mask_past].apply(ajuster_ev, axis=1)

# Sauvegarde
df.to_csv(output_file, sep=";", index=False, float_format="%.2f")

print(f"Fichier généré : {output_file}")
print(f"{len(df)} lignes au total.")
print("Extrapolation appliquée pour les années 1901–1946.")