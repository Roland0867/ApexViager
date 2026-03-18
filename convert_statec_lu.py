import pandas as pd
from pathlib import Path

# Dossier du projet
BASE_DIR = Path(__file__).resolve().parent

# Fichier officiel STATEC (téléchargé)
input_file = BASE_DIR / "tables_esperance_vie_officielles.csv"

# Fichier de sortie au format ApexViager
output_file = BASE_DIR / "tables_esperance_vie_LU.csv"

# Lecture du fichier STATEC (séparateur ;)
df = pd.read_csv(input_file, sep=";")

# On garde les colonnes importantes (adaptées à la structure officielle)
# Colonnes vues dans ton fichier : SEX;Sexe;AGE;Age;TIME_PERIOD;Période;OBS_VALUE;Valeur
df = df[["SEX", "AGE", "TIME_PERIOD", "OBS_VALUE"]]

# Mapping SEX -> M/F (à adapter si besoin)
sex_map = {
    "S01": "M",  # Hommes (si c'est le code utilisé)
    "S02": "F",  # Femmes
}

df["sexe"] = df["SEX"].map(sex_map)
df = df[df["sexe"].notna()]

# Conversion AGE code -> âge numérique
def code_age_to_int(code):
    # Exemple: 'SL04' -> '04' -> 4
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if digits == "":
        return None
    return int(digits)

df["age"] = df["AGE"].apply(code_age_to_int)
df = df[df["age"].notna()]

# Construction des colonnes pour ApexViager
df["pays"] = "LU"
df["source_officielle"] = "STATEC"
df["annee_reference"] = df["TIME_PERIOD"].astype(int)
df["esperance_vie_restante"] = df["OBS_VALUE"]
df["date_publication_source"] = "2024-01-01"  # à ajuster si tu as la vraie date
df["actif"] = True

# Colonnes finales dans l'ordre attendu par l'import
df_final = df[
    [
        "pays",
        "source_officielle",
        "annee_reference",
        "sexe",
        "age",
        "esperance_vie_restante",
        "date_publication_source",
        "actif",
    ]
]

# Sauvegarde CSV pour l'import admin
df_final.to_csv(output_file, sep=";", index=False, float_format="%.2f")

print(f"Fichier généré : {output_file}")
print(f"{len(df_final)} lignes exportées.")
