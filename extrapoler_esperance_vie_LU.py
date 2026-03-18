import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
input_file = BASE_DIR / "tables_esperance_vie_LU.csv"
output_file = BASE_DIR / "tables_esperance_vie_LU_full.csv"

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

# Remplacer la virgule décimale par un point puis convertir en float
df["esperance_vie_restante"] = (
    df["esperance_vie_restante"]
    .astype(str)
    .str.replace(",", ".", regex=False)
    .astype(float)
)


rows = []

# on limite, par prudence, à 0–100 ans
min_age = 0
max_age = 100

for (annee, sexe), grp in df.groupby(["annee_reference", "sexe"]):
    grp_sorted = grp.sort_values("age")

    # âges réellement observés pour cette année+sexe
    observed_ages = grp_sorted["age"].tolist()

    # série d'âges complète
    all_ages = pd.Series(range(min_age, max_age + 1), name="age")

    # mettre l'âge en index
    g = grp_sorted.set_index("age")["esperance_vie_restante"]

    # interpolation linéaire seulement entre le min et le max observés
    g_full = g.reindex(all_ages)
    g_full = g_full.interpolate(method="linear", limit_direction="both")

    # en dehors de la plage observée, on laisse NaN
    # min et max observés :
    min_obs = min(observed_ages)
    max_obs = max(observed_ages)
    g_full.loc[: min_obs - 1] = float("nan")
    g_full.loc[max_obs + 1 :] = float("nan")

    for age in all_ages:
        val = g_full.loc[age]

        # on n'enregistre que les âges avec une valeur définie
        if pd.isna(val):
            continue

        rows.append(
            {
                "pays": grp_sorted["pays"].iloc[0],
                "source_officielle": grp_sorted["source_officielle"].iloc[0],
                "annee_reference": annee,
                "sexe": sexe,
                "age": int(age),
                "esperance_vie_restante": float(val),
                "date_publication_source": grp_sorted["date_publication_source"].iloc[0],
                "actif": grp_sorted["actif"].iloc[0],
            }
        )

df_full = pd.DataFrame(rows)
df_full.sort_values(["annee_reference", "sexe", "age"], inplace=True)

df_full.to_csv(output_file, sep=";", index=False, float_format="%.2f")

print(f"Fichier généré : {output_file}")
print(f"{len(df_full)} lignes exportées.")

