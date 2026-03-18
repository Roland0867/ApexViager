import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
input_file = BASE_DIR / "tables_esperance_vie_LU_full.csv"
output_file = BASE_DIR / "tables_esperance_vie_LU_1901_2025.csv"

df = pd.read_csv(input_file, sep=";")

required_cols = [
    "pays",
    "source_officielle",
    "annee_reference",
    "sexe",
    "age",
    "esperance_vie_restante",
    "date_publication_source",
    "actif",
]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    raise ValueError(f"Colonnes manquantes dans le CSV: {missing}")

df["annee_reference"] = df["annee_reference"].astype(int)
df["age"] = df["age"].astype(int)
df["esperance_vie_restante"] = (
    df["esperance_vie_restante"]
    .astype(str)
    .str.replace(",", ".", regex=False)
    .astype(float)
)

# années officielles disponibles, triées
years_official = sorted(df["annee_reference"].unique())
first_year = min(years_official)
last_year = max(years_official)

print(f"Années officielles disponibles : {years_official}")
print(f"Première année : {first_year}, dernière année : {last_year}")

rows = []

# on veut couvrir de 1901 à 2025
for year in range(1901, 2026):
    # trouver la dernière année officielle <= year
    source_years = [y for y in years_official if y <= year]
    if not source_years:
        # si year est avant la première année officielle,
        # on utilise la première année officielle
        ref_year = first_year
    else:
        ref_year = max(source_years)

    # filtrer les lignes de cette année de référence
    subset = df[df["annee_reference"] == ref_year]

    for _, row in subset.iterrows():
        rows.append(
            {
                "pays": row["pays"],
                "source_officielle": row["source_officielle"],
                "annee_reference": year,  # année étendue
                "sexe": row["sexe"],
                "age": int(row["age"]),
                "esperance_vie_restante": float(row["esperance_vie_restante"]),
                "date_publication_source": row["date_publication_source"],
                "actif": row["actif"],
            }
        )

df_extended = pd.DataFrame(rows)
df_extended.sort_values(["annee_reference", "sexe", "age"], inplace=True)

df_extended.to_csv(output_file, sep=";", index=False, float_format="%.2f")

print(f"Fichier généré : {output_file}")
print(f"{len(df_extended)} lignes exportées.")
