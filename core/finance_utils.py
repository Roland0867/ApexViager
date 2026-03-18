from decimal import Decimal, getcontext
from datetime import date

# On augmente un peu la précision décimale
getcontext().prec = 10


def calcul_van(taux_actualisation: Decimal, flux: list[Decimal]) -> Decimal:
    """
    Calcule la VAN à partir d'un taux (ex. 0.05 pour 5%)
    et d'une liste de flux annuels [CF0, CF1, ..., CFn].
    """
    van = Decimal("0")
    for t, cf in enumerate(flux):
        van += cf / (Decimal("1") + taux_actualisation) ** t
    return van


def calcul_tri(flux: list[Decimal], tolerance: Decimal = Decimal("0.0001")) -> Decimal | None:
    """
    Calcule approximativement le TRI (taux qui annule la VAN)
    par dichotomie entre 0% et 50%. Retourne None si non trouvé.
    """
    # On impose qu'il y ait au moins un flux négatif et un positif
    if not flux or all(cf >= 0 for cf in flux) or all(cf <= 0 for cf in flux):
        return None

    bas = Decimal("0.0")
    haut = Decimal("0.5")  # 50%
    van_bas = calcul_van(bas, flux)
    van_haut = calcul_van(haut, flux)

    # Si la VAN a le même signe aux deux bords, on renonce
    if van_bas * van_haut > 0:
        return None

    # Recherche dichotomique
    while haut - bas > tolerance:
        milieu = (bas + haut) / 2
        van_milieu = calcul_van(milieu, flux)
        if van_milieu == 0:
            return milieu
        # On cherche un changement de signe
        if van_bas * van_milieu < 0:
            haut = milieu
            van_haut = van_milieu
        else:
            bas = milieu
            van_bas = van_milieu

    return (bas + haut) / 2

def calcul_age(date_naissance: date, date_reference: date) -> int:
    """Calcule l'âge en années révolues à une date donnée."""
    if not date_naissance or not date_reference:
        return None
    years = date_reference.year - date_naissance.year
    if (date_reference.month, date_reference.day) < (date_naissance.month, date_naissance.day):
        years -= 1
    return years


def get_esperance_vie(pays: str, sexe: str, age: int) -> float | None:
    if age is None:
        return None

    from .models import TableEsperanceVie

    # Normalisation pays vers les libellés de la table
    if pays in ["LU", "Luxembourg", "Luxembourgeoise"]:
        pays_filtre = "Luxembourg"
    elif pays in ["DE", "Deutschland", "Allemand", "Allemande", "Allemagne"]:
        pays_filtre = "Allemagne"
    else:
        pays_filtre = pays

    # Normalisation sexe vers 'Homme' / 'Femme'
    if sexe in ["M", "m"]:
        sexe_filtre = "Homme"
    elif sexe in ["F", "f"]:
        sexe_filtre = "Femme"
    else:
        sexe_filtre = sexe

    qs = TableEsperanceVie.objects.filter(
        pays=pays_filtre,
        sexe=sexe_filtre,
        age=age,
        actif=True,
    ).order_by("-annee_reference")

    if not qs.exists():
        return None

    return float(qs.first().esperance_vie_restante)
