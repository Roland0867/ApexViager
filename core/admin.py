from django.contrib import admin, messages
from django.conf import settings
from django.shortcuts import redirect
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django import forms

import csv
import datetime
from decimal import Decimal
from pathlib import Path

from django.utils.safestring import mark_safe

from .finance_utils import calcul_age, get_esperance_vie, calcul_van, calcul_tri
from .models import (
    Proprietaire,
    Bien,
    ExtraitCadastral,
    Parcelle,
    DossierViager,
    ScenarioViager,
    ParametresPays,
    TableEsperanceVie,
)

# ---------------------------------------------------
# Paramètres pays
# ---------------------------------------------------

@admin.register(ParametresPays)
class ParametresPaysAdmin(admin.ModelAdmin):
    list_display = (
        "pays",
        "rendement_cible",
        "frais_annuels_hors_rendement",
        "total_frais_annuels",
        "total_frais_uniques",
    )

    readonly_fields = (
        "frais_annuels_hors_rendement",
        "total_frais_annuels",
        "total_frais_uniques",
    )

    fieldsets = (
        ("Identification", {
            "fields": ("pays",),
        }),
        ("Valeur annuelle du droit d'habitation", {
            "fields": ("rendement_cible",),
        }),
        ("Frais annuels", {
            "fields": (
                "entretien_annuel_proprietaire",
                "frais_fixes_proprietaire",
                "frais_fis_annuel",
                "frais_gm_annuel",
                "frais_compte_bancaire",
                "frais_annuels_hors_rendement",
            ),
        }),
        ("Frais uniques", {
            "fields": (
                "frais_agence",
                "frais_notaire",
                "ouverture_dossier_fis",
                "ouverture_dossier_gm",
            ),
        }),
        ("Synthèse", {
            "fields": (
                "total_frais_annuels",
                "total_frais_uniques",
            ),
        }),
    )

    def frais_annuels_hors_rendement(self, obj):
        if not obj:
            return ""
        return (
            obj.entretien_annuel_proprietaire
            + obj.frais_fixes_proprietaire
            + obj.frais_fis_annuel
            + obj.frais_gm_annuel
            + obj.frais_compte_bancaire
        )

    frais_annuels_hors_rendement.short_description = "Frais annuels hors rendement (%)"

    def total_frais_annuels(self, obj):
        if not obj:
            return ""
        return obj.rendement_cible + self.frais_annuels_hors_rendement(obj)

    total_frais_annuels.short_description = "Total frais annuels (%)"

    def total_frais_uniques(self, obj):
        if not obj:
            return ""
        return obj.ouverture_dossier_fis + obj.ouverture_dossier_gm

    total_frais_uniques.short_description = "Total frais uniques (€)"

# ---------------------------------------------------
# Propriétaires
# ---------------------------------------------------

class AgeAcuelListFilter(admin.SimpleListFilter):
    title = "Âge actuel"
    parameter_name = "age_actuel"

    def lookups(self, request, model_admin):
        return [
            ("-60", "Moins de 60 ans"),
            ("60-70", "60 à 70 ans"),
            ("70-80", "70 à 80 ans"),
            ("80-90", "80 à 90 ans"),
            ("90+", "90 ans et plus"),
        ]
    
    def queryset(self, request, queryset):
        if self.value() == "-60":
            return queryset.filter(age_actuel__lt=60)
        if self.value() == "60-70":
            return queryset.filter(age_actuel__gte=60, age_actuel__lt=70)
        if self.value() == "70-80":
            return queryset.filter(age_actuel__gte=70, age_actuel__lt=80)
        if self.value() == "80-90":
            return queryset.filter(age_actuel__gte=80, age_actuel__lt=90)
        if self.value() == "90+":
            return queryset.filter(age_actuel__gte=90)
        return queryset

class EsperanceVieListFilter(admin.SimpleListFilter):
    title = "Espérance de vie"
    parameter_name = "esperance_vie"

    def lookups(self, request, model_admin):
        return [
            ("-5", "Moins de 5 ans"),
            ("5-10", "5 à 10 ans"),
            ("10-15", "10 à 15 ans"),
            ("15-20", "15 à 20 ans"),
            ("20+", "20 ans et plus"),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if self.value() == "-5":
            return queryset.filter(esperance_vie__lt=5)
        if self.value() == "5-10":
            return queryset.filter(esperance_vie__gte=5, esperance_vie__lt=10)
        if self.value() == "10-15":
            return queryset.filter(esperance_vie__gte=10, esperance_vie__lt=15)
        if self.value() == "15-20":
            return queryset.filter(esperance_vie__gte=15, esperance_vie__lt=20)
        if self.value() == "20+":
            return queryset.filter(esperance_vie__gte=20)
        return queryset

@admin.register(Proprietaire)
class ProprietaireAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {
            "fields": (
                "nom",
                "prenom",
                "rue_numero",
                ("code_postal", "ville"),
                "canton_etat",
                "pays",
                "date_naissance",
                "nationalite",
                "sexe",
                "telephone",
                "email",
                "age_actuel", # champ readonly
                "esperance_vie", # champ readonly
                "biens_du_proprietaire", # champ readonly
            )
        }),
    )
    readonly_fields = ("age_actuel", "esperance_vie", "biens_du_proprietaire")

    # Colonnes de la liste
    list_display = ("proprietaire_label", "pays", "age_actuel", "esperance_vie")

    # Filtres de la liste
    list_filter = ("pays", AgeAcuelListFilter, EsperanceVieListFilter)
    
    # Barre de recherche (nom/prénom)
    search_fields = ("nom", "prenom")

    # Tri par défaut (nom, puis prénom)
    ordering = ("nom", "prenom")

    def biens_du_proprietaire(self, obj):
         if not obj or not obj.pk:
             return "Enregistrez le propriétaire pour voir les biens."

         biens = obj.biens.all()
         if not biens:
             return "Aucun bien lié à ce propriétaire."

         lignes = [
             "<table style='border-collapse: collapse; width: 100%;'>"
             "<thead><tr>"
                "<th style='border: 1px solid #ccc; padding: 4px;'>Bien</th>"
                "<th style='border: 1px solid #ccc; padding: 4px;'>Pays</th>"
                "<th style='border: 1px solid #ccc; padding: 4px;'>Ville</th>"
                "<th style='border: 1px solid #ccc; padding: 4px;'>Valeur vénale</th>"
             "</tr></thead><tbody>"
         ]

         for bien in biens:
             # URL de la fiche admin du bien
             info = (bien._meta.app_label, bien._meta.model_name)
             url = reverse("admin:%s_%s_change" % info, args=[bien.pk,])
                                                              
             lignes.append(
                 "<tr>"
                 f"<td style='border: 1px solid #ccc; padding: 4px;'>"
                 f"<a href='{url}'>{bien}</a></td>"
                 f"<td style='border: 1px solid #ccc; padding: 4px;'>{bien.pays}</td>"
                 f"<td style='border: 1px solid #ccc; padding: 4px;'>{bien.ville}</td>"
                 f"<td style='border: 1px solid #ccc; padding: 4px;'>{getattr(bien, 'valeur_venale', '')}</td>"
                 "</tr>"
             )

         lignes.append("</tbody></table>")
         html = "".join(lignes)
         return mark_safe(html)   # <- AUCUN format_html ici

    biens_du_proprietaire.short_description = "Biens associés"

    def proprietaire_label(self, obj):
        return f"{obj.nom} {obj.prenom}".strip()
    proprietaire_label.short_description = "Propriétaire"

    # Titre de l'écran

    def changelist_view(self, request, extra_context = None):
        extra_context = extra_context or {}
        extra_context["title"] = "Propriétaires"
        return super().changelist_view(request, extra_context=extra_context)
    
    def changeform_view(self, request, object_id = None, form_url = ..., extra_context = None):
        extra_context = extra_context or {}
        extra_context["title"] = "Fiche propriétaire"
        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context
        )

# ---------------------------------------------------
# Biens
# ---------------------------------------------------

class ParcelleInline(admin.TabularInline):
    model = Parcelle
    extra = 1


@admin.register(ExtraitCadastral)
class ExtraitCadastralAdmin(admin.ModelAdmin):
    list_display = ("bien", "pays", "commune", "section", "date_emission", "reference")
    search_fields = ("bien__adresse", "commune", "section", "reference")
    list_filter = ("pays", "commune")

    inlines = [ParcelleInline]

class ExtraitCadastralInline(admin.StackedInline):
    model = ExtraitCadastral
    extra = 1
    
@admin.register(Bien)
class BienAdmin(admin.ModelAdmin):
    list_display = (
        "type_bien",
        "categorie_logement",
        "adresse",
        "ville",
        "pays",
        "surface_habitable",
    )
    list_filter = ("type_bien", "categorie_logement", "pays")
    search_fields = ("adresse", "ville", "donnees_cadastrales")
    filter_horizontal = ("proprietaires",)

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "type_bien",
                    "categorie_logement",
                    "adresse",
                    ("code_postal", "ville"),
                    "pays",
                    "surface_habitable",
                    "surface_utile",
                    "superficie_terrain",
                    # "donnees_cadastrales",
                    "annee_construction",
                    "etat",
                    "loyer_actuel",
                    "valeur_locative",
                    "valeur_venale_estimee",
                    "valeur_reelle",
                    "cpe",
                    "charges_locataire",
                    "investissements_travaux_prevus",
                    "situation_pag_pap",
                    "syndic",
                    "proprietaires",          # M2M éditable
                    "proprietaires_du_bien",  # tableau readonly
                )
            },
        ),
    )

    readonly_fields = ("proprietaires_du_bien",)

    inlines = [ExtraitCadastralInline]

    def proprietaires_du_bien(self, obj):
        if not obj or not obj.pk:
            return "Enregistrez le bien pour voir les propriétaires."

        proprietaires = obj.proprietaires.all()
        if not proprietaires:
            return "Aucun propriétaire lié à ce bien."

        lignes = [
            "<table style='border-collapse: collapse; width: 100%;'>"
            "<thead><tr>"
            "<th style='border: 1px solid #ccc; padding: 4px;'>Propriétaire</th>"
            "<th style='border: 1px solid #ccc; padding: 4px;'>Pays</th>"
            "<th style='border: 1px solid #ccc; padding: 4px;'>Ville</th>"
            "</tr></thead><tbody>"
        ]

        for prop in proprietaires:
            info = (prop._meta.app_label, prop._meta.model_name)
            url = reverse("admin:%s_%s_change" % info, args=[prop.pk])

            lignes.append(
                "<tr>"
                f"<td style='border: 1px solid #ccc; padding: 4px;'>"
                f"<a href='{url}'>{prop.nom} {prop.prenom}</a></td>"
                f"<td style='border: 1px solid #ccc; padding: 4px;'>{prop.pays}</td>"
                f"<td style='border: 1px solid #ccc; padding: 4px;'>{prop.ville}</td>"
                "</tr>"
            )

        lignes.append("</tbody></table>")
        return mark_safe("".join(lignes))

    proprietaires_du_bien.short_description = "Propriétaires associés"

    inlines = [ExtraitCadastralInline]

# ---------------------------------------------------
# Utilitaires EV pour DossierViager / Scénarios
# ---------------------------------------------------

def calculer_esperance_vie_pour_dossier(dossier):
    """
    Calcule EV à la signature pour le crédirentier le plus jeune
    et met à jour le dossier (age_signature, esperance_vie_signature).
    """
    bien = dossier.bien

    proprietaires = list(bien.proprietaires.all())
    if not proprietaires or not dossier.date_signature:
        return None

    ages = []
    for p in proprietaires:
        if p.date_naissance:
            ages.append((p, calcul_age(p.date_naissance, dossier.date_signature)))

    if not ages:
        return None

    # crédirentier le plus jeune
    proprietaire_jeune, age_jeune = min(ages, key=lambda t: t[1])

    ev = get_esperance_vie(bien.pays, proprietaire_jeune.sexe, age_jeune)
    if ev is None:
        return None

    dossier.age_signature = age_jeune
    dossier.esperance_vie_signature = ev
    dossier.save(update_fields=["age_signature", "esperance_vie_signature"])

    return ev  # EV restante en années


@admin.action(description="Calculer l'espérance de vie à la signature")
def calculer_esperance_vie_signature_action(modeladmin, request, queryset):
    for dossier in queryset:
        calculer_esperance_vie_pour_dossier(dossier)


# ---------------------------------------------------
# Dossiers de viager
# ---------------------------------------------------

@admin.register(DossierViager)
class DossierViagerAdmin(admin.ModelAdmin):
    model = DossierViager
    verbose_name = "Dossier de viager"
    verbose_name_plural = "Dossiers de viager"

    list_display = ("id", "bien", "type_viager", "parametres_pays", "date_creation")
    list_filter = ("type_viager", "date_creation", "parametres_pays")
    search_fields = ("bien__adresse", "bien__ville")
    actions = [
        "creer_scenarios_simples",
        calculer_esperance_vie_signature_action,
    ]

    readonly_fields = ("infos_proprietaires", "duree_indicative_viager")

    fieldsets = (
        (None, {
            "fields": (
                "bien",
                "type_viager",
                "description_interne",
                "parametres_pays",
                "date_signature",
                "infos_proprietaires",
                "duree_indicative_viager",
            )
        }),
    )

    def infos_proprietaires(self, obj):
        """
        Nom, Prénom, âge actuel et EV de chaque propriétaire du bien.
        """
        if not obj or not obj.bien_id:
            return "Aucun bien sélectionné."

        lignes = []
        for p in obj.bien.proprietaires.all():
            lignes.append(
                f"{p.nom} {p.prenom} - âge {p.age_actuel} ans - EV restante {p.esperance_vie} ans"
            )

        return "<br>".join(lignes) if lignes else "Aucun propriétaire associé."

    infos_proprietaires.short_description = "Propriétaires (âge actuel + EV)"
    infos_proprietaires.allow_tags = True  # uniquement si tu utilises le rendu HTML

    def age_actuel(self, obj):
        """
        Âge actuel du crédirentier le plus jeune (à la date du jour).
        """
        bien = obj.bien
        proprietaires = list(bien.proprietaires.all())
        if not proprietaires:
            return None

        today = timezone.now().date()
        ages = [
            calcul_age(p.date_naissance, today)
            for p in proprietaires
            if p.date_naissance
        ]
        if not ages:
            return None
        return min(ages)

    age_actuel.short_description = "Age actuel"

    def duree_indicative_viager(self, obj):
        """
        Durée indicative = EV la plus longue parmi les propriétaires.
        """
        if not obj or not obj.bien_id:
            return None

        bien = obj.bien
        proprietaires = list(bien.proprietaires.all())
        if not proprietaires:
            return None

        evs = []
        for p in proprietaires:
            if p.age_actuel is not None:
                ev = get_esperance_vie(bien.pays, p.sexe, p.age_actuel)
                if ev is not None:
                    evs.append(ev)

        if not evs:
            return None

        return max(evs)

    duree_indicative_viager.short_description = "Durée indicative du viager (années)"

    def creer_scenarios_simples(self, request, queryset):
        """
        Créer un scénario simple (bouquet 20 %, rente 4 %/an) pour chaque dossier.
        """
        created_total = 0

        for dossier in queryset:
            bien = dossier.bien
            if not bien.valeur_venale_estimee:
                messages.warning(
                    request,
                    f"Dossier {dossier.id}: valeur vénale estimée manquante, scénario ignoré.",
                )
                continue

            valeur_venale = bien.valeur_venale_estimee

            bouquet_pct = Decimal("0.20")
            bouquet = valeur_venale * bouquet_pct

            rente_annuelle = valeur_venale * Decimal("0.04")
            rente_mensuelle = rente_annuelle / Decimal("12")

            if rente_mensuelle < Decimal("100"):
                rente_mensuelle = Decimal("100")

            ScenarioViager.objects.create(
                dossier=dossier,
                nom_scenario="Scénario simple 20% / 4%",
                type_scenario="CLASSIQUE",
                bouquet_pourcent=bouquet_pct,
                bouquet_montant=bouquet,
                rente_viagere_mensuelle=rente_mensuelle,
                tri=None,
                van=None,
                statut="EN_SUSPENS",
            )
            created_total += 1

        messages.success(
            request,
            f"{created_total} scénario(x) simple(s) ont été créés.",
        )

    creer_scenarios_simples.short_description = "Créer un scénario simple"


# ---------------------------------------------------
# Scénarios
# ---------------------------------------------------

@admin.register(ScenarioViager)
class ScenarioViagerAdmin(admin.ModelAdmin):
    list_display = (
        "nom_scenario",
        "dossier",
        "type_scenario",
        "bouquet_pourcent",
        "bouquet_montant_euros",
        "rente_viagere_mensuelle_euros",
        "tri_pourcent",
        "van_euros",
        "investissement_initial_euros",
        "enveloppe_credirentier_euros",
        "cout_annuel_total_euros",
        "plafond_60_ok",
        "statut",
        "date_calcul",
    )
    list_filter = ("type_scenario", "statut")
    search_fields = ("nom_scenario", "dossier__bien__adresse")

    actions = ["calculer_van_et_tri", "calculer_ev_van_tri"]

    def bouquet_montant_euros(self, obj):
        if obj.bouquet_montant is None:
            return ""
        return f"{obj.bouquet_montant:,.2f} €".replace(",", " ").replace(".", ",")

    bouquet_montant_euros.short_description = "Bouquet (€)"

    def rente_viagere_mensuelle_euros(self, obj):
        if obj.rente_viagere_mensuelle is None:
            return ""
        return f"{obj.rente_viagere_mensuelle:,.2f} €".replace(",", " ").replace(".", ",")

    rente_viagere_mensuelle_euros.short_description = "Rente mensuelle (€)"

    def tri_pourcent(self, obj):
        if obj.tri is None:
            return ""
        valeur = obj.tri * Decimal("100")
        return f"{valeur:.2f} %"

    tri_pourcent.short_description = "TRI"

    def van_euros(self, obj):
        if obj.van is None:
            return ""
        return f"{obj.van:,.2f} €".replace(",", " ").replace(".", ",")

    van_euros.short_description = "VAN (€)"

    def investissement_initial_euros(self, obj):
        if obj.investissement_initial is None:
            return ""
        return f"{obj.investissement_initial:,.2f} €".replace(",", " ").replace(".", ",")

    investissement_initial_euros.short_description = "Invest. initial (€)"

    def enveloppe_credirentier_euros(self, obj):
        if obj.enveloppe_credirentier is None:
            return ""
        return f"{obj.enveloppe_credirentier:,.2f} €".replace(",", " ").replace(".", ",")

    enveloppe_credirentier_euros.short_description = "Enveloppe crédirentier (€)"

    def cout_annuel_total_euros(self, obj):
        if obj.cout_annuel_total is None:
            return ""
        return f"{obj.cout_annuel_total:,.2f} €".replace(",", " ").replace(".", ",")

    cout_annuel_total_euros.short_description = "Frais annuels (€)"

    def plafond_60_ok(self, obj):
        return "OK" if obj.respecte_plafond_60 else "> 60%"

    plafond_60_ok.short_description = "Invest. ≤ 60 %"

    # ----- Actions de calcul -----

    def calculer_ev_van_tri(self, request, queryset):
        """
        Calcule EV (via dossier) + VAN / TRI pour les scénarios sélectionnés.
        """
        horizon = 20
        maj = 0
        sans_param = 0

        queryset = queryset.select_related("dossier", "dossier__parametres_pays", "dossier__bien")

        for scenario in queryset:
            dossier = scenario.dossier

            # 1) EV à la signature sur le dossier
            ev = calculer_esperance_vie_pour_dossier(dossier)

            if ev is not None:
                scenario.duree_rente_temporaire_annees = int(round(ev))
                scenario.save(update_fields=["duree_rente_temporaire_annees"])

            # 2) VAN / TRI
            if scenario.bouquet_montant is None or scenario.rente_viagere_mensuelle is None:
                continue

            params = getattr(dossier, "parametres_pays", None)
            if params is None:
                sans_param += 1
                continue

            taux_actualisation = params.rendement_cible / Decimal("100")

            bien = dossier.bien
            valeur_venale = bien.valeur_venale_estimee or Decimal("0")

            frais_acquisition = Decimal("0")
            if valeur_venale:
                frais_acquisition = valeur_venale * (
                    params.frais_agence + params.frais_notaire
                ) / Decimal("100")

            investissement_initial = scenario.bouquet_montant + frais_acquisition

            flux = []
            flux.append(-scenario.bouquet_montant - frais_acquisition)

            rente_mensuelle = scenario.rente_viagere_mensuelle
            if rente_mensuelle < Decimal("100"):
                rente_mensuelle = Decimal("100")

            rente_annuelle = rente_mensuelle * Decimal("12")

            cout_annuel_propriete = Decimal("0")
            if valeur_venale:
                cout_annuel_propriete = valeur_venale * (
                    params.entretien_annuel_proprietaire + params.frais_fixes_proprietaire
                ) / Decimal("100")

            cout_annuel_structure = Decimal("0")
            if investissement_initial:
                cout_annuel_structure = investissement_initial * (
                    params.frais_fis_annuel + params.frais_gm_annuel + params.frais_compte_bancaire
                ) / Decimal("100")

            cout_annuel_total = cout_annuel_propriete + cout_annuel_structure

            for _ in range(1, horizon + 1):
                flux.append(rente_annuelle + cout_annuel_total)

            van = calcul_van(taux_actualisation, flux)
            tri = calcul_tri(flux)

            flux_cred = [scenario.bouquet_montant]
            for _ in range(1, horizon + 1):
                flux_cred.append(rente_annuelle)

            enveloppe_cred = calcul_van(taux_actualisation, flux_cred)

            if valeur_venale:
                plafond_60 = valeur_venale * Decimal("0.60")
                respecte_plafond_60 = investissement_initial <= plafond_60
            else:
                respecte_plafond_60 = False

            scenario.van = van
            scenario.tri = tri
            scenario.investissement_initial = investissement_initial
            scenario.enveloppe_credirentier = enveloppe_cred
            scenario.cout_annuel_total = cout_annuel_total
            scenario.respecte_plafond_60 = respecte_plafond_60
            scenario.save(
                update_fields=[
                    "van",
                    "tri",
                    "investissement_initial",
                    "enveloppe_credirentier",
                    "cout_annuel_total",
                    "respecte_plafond_60",
                ]
            )
            maj += 1

        if maj:
            messages.success(request, f"EV + VAN/TRI recalculés pour {maj} scénario(x).")
        if sans_param:
            messages.warning(
                request,
                f"{sans_param} scénario(x) ignoré(s) car le dossier n'a pas de paramètres pays."
            )

    calculer_ev_van_tri.short_description = "Calculer EV + VAN/TRI"

    def calculer_van_et_tri(self, request, queryset):
        """
        Version simple : seulement VAN / TRI (sans recalcul EV).
        """
        horizon = 20
        maj = 0
        sans_param = 0

        queryset = queryset.select_related("dossier", "dossier__parametres_pays", "dossier__bien")

        for scenario in queryset:
            if scenario.bouquet_montant is None or scenario.rente_viagere_mensuelle is None:
                continue

            dossier = scenario.dossier
            params = getattr(dossier, "parametres_pays", None)

            if params is None:
                sans_param += 1
                continue

            taux_actualisation = params.rendement_cible / Decimal("100")

            bien = dossier.bien
            valeur_venale = bien.valeur_venale_estimee or Decimal("0")

            frais_acquisition = Decimal("0")
            if valeur_venale:
                frais_acquisition = valeur_venale * (
                    params.frais_agence + params.frais_notaire
                ) / Decimal("100")

            investissement_initial = scenario.bouquet_montant + frais_acquisition

            flux = []
            flux.append(-scenario.bouquet_montant - frais_acquisition)

            rente_mensuelle = scenario.rente_viagere_mensuelle
            if rente_mensuelle < Decimal("100"):
                rente_mensuelle = Decimal("100")

            rente_annuelle = rente_mensuelle * Decimal("12")

            cout_annuel_propriete = Decimal("0")
            if valeur_venale:
                cout_annuel_propriete = valeur_venale * (
                    params.entretien_annuel_proprietaire + params.frais_fixes_proprietaire
                ) / Decimal("100")

            cout_annuel_structure = Decimal("0")
            if investissement_initial:
                cout_annuel_structure = investissement_initial * (
                    params.frais_fis_annuel + params.frais_gm_annuel + params.frais_compte_bancaire
                ) / Decimal("100")

            cout_annuel_total = cout_annuel_propriete + cout_annuel_structure

            for _ in range(1, horizon + 1):
                flux.append(rente_annuelle + cout_annuel_total)

            van = calcul_van(taux_actualisation, flux)
            tri = calcul_tri(flux)

            flux_cred = [scenario.bouquet_montant]
            for _ in range(1, horizon + 1):
                flux_cred.append(rente_annuelle)

            enveloppe_cred = calcul_van(taux_actualisation, flux_cred)

            if valeur_venale:
                plafond_60 = valeur_venale * Decimal("0.60")
                respecte_plafond_60 = investissement_initial <= plafond_60
            else:
                respecte_plafond_60 = False

            scenario.van = van
            scenario.tri = tri
            scenario.investissement_initial = investissement_initial
            scenario.enveloppe_credirentier = enveloppe_cred
            scenario.cout_annuel_total = cout_annuel_total
            scenario.respecte_plafond_60 = respecte_plafond_60
            scenario.save(
                update_fields=[
                    "van",
                    "tri",
                    "investissement_initial",
                    "enveloppe_credirentier",
                    "cout_annuel_total",
                    "respecte_plafond_60",
                ]
            )
            maj += 1

        if maj:
            messages.success(request, f"VAN/TRI recalculés pour {maj} scénario(x).")
        if sans_param:
            messages.warning(
                request,
                f"{sans_param} scénario(x) ignoré(s) car le dossier n'a pas de paramètres pays."
            )

    calculer_van_et_tri.short_description = "Calculer VAN et TRI (avec paramètres pays)"


# ---------------------------------------------------
# Table d'espérance de vie
# (imports CSV, auto-STATEC, LU 2023)
# ---------------------------------------------------

class ImportEsperanceVieForm(forms.Form):
    csv_file = forms.FileField(
        label="Fichier CSV (séparateur ;)",
        help_text="Colonnes: pays;source_officielle;annee_reference;sexe;age;esperance_vie_restante;date_publication_source;actif",
    )

@admin.register(TableEsperanceVie)
class TableEsperanceVieAdmin(admin.ModelAdmin):
    list_display = (
        "pays",
        "annee_reference",
        "source_officielle",
        "sexe",
        "age",
        "esperance_vie_restante",
        "date_publication_source",
        "actif",
    )
    list_filter = ("pays", "annee_reference", "sexe", "actif")
    search_fields = ("source_officielle",)
    ordering = ("pays", "annee_reference", "sexe", "age")

    fields = (
        "pays",
        "source_officielle",
        "annee_reference",
        "sexe",
        "age",
        "esperance_vie_restante",
        "date_publication_source",
        "actif",
    )

        # Template liste avec bouton custom
    change_list_template = "admin/core/tableesperancevie_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-lu-2023/",
                self.admin_site.admin_view(self.import_lu_2023),
                name="core_tableesperancevie_import_lu_2023",
            ),
            path(
                "import-de-2023/",
                self.admin_site.admin_view(self.import_de_2023),
                name="core_tableesperancevie_import_de_2023",
            ),
        ]
        return custom_urls + urls
    
    def import_lu_2023(self, request):
        """
        Importe directement 'Esperance_Vie_LU_2023.csv' (format STATEC brut)
        et alimente TableEsperanceVie pour le Luxembourg, année 2023.
        """
        BASE_DIR = Path(__file__).resolve().parent.parent  # C:\ApexViager
        input_file = BASE_DIR / "Esperance_Vie_LU_2023.csv"

        if not input_file.exists():
            messages.error(
                request,
                f"Fichier introuvable : {input_file}. Place 'Esperance_Vie_LU_2023.csv' à la racine du projet.",
            )
            from django.shortcuts import redirect
            return redirect("admin:core_tableesperancevie_changelist")

        # mapping des codes STATEC -> sexe M/F
        sex_map = {
            "B01": "M",  # Hommes
            "B02": "F",  # Femmes
        }

        def code_age_to_int(code: str) -> int | None:
            # ex: "SL003" -> 3, "SL071" -> 71
            digits = "".join(ch for ch in str(code) if ch.isdigit())
            if not digits:
                return None
            return int(digits)

        created = 0
        updated = 0

        with input_file.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            for row in reader:
                try:
                    sexe_code = row.get("SEX")
                    age_code = row.get("AGE")
                    periode = row.get("TIME_PERIOD")
                    ev_str = row.get("OBS_VALUE")

                    sexe = sex_map.get(sexe_code)
                    age = code_age_to_int(age_code)

                    if sexe is None or age is None or not ev_str:
                        continue

                    # valeur EV en float
                    esperance_vie_restante = float(ev_str.replace(",", "."))

                    # année de référence = TIME_PERIOD (ex: 2023)
                    annee_ref = int(periode)

                    obj, was_created = TableEsperanceVie.objects.update_or_create(
                        pays="Luxembourg",
                        annee_reference=annee_ref,
                        sexe="Homme" if sexe == "M" else "Femme",
                        age=age,
                        defaults={
                            "source_officielle": "STATEC",
                            "esperance_vie_restante": esperance_vie_restante,
                            "date_publication_source": datetime(2023, 1, 1).date(),
                            "actif": True,
                        },
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                except Exception as e:
                    messages.error(request, f"Erreur ligne CSV: {row} -> {e}")

        from django.shortcuts import redirect
        messages.success(
            request,
            f"Import LU 2023 terminé : {created} créés, {updated} mis à jour."
        )
        return redirect("admin:core_tableesperancevie_changelist")
    
    def import_de_2023(self, request):
        created = 0
        updated = 0

        csv_path = settings.BASE_DIR / "Esperance_Vie_DE_2023.csv"

        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")

            # sauter la ligne d'en-tête
            headers = next(reader, None)

            for row in reader:
                if not row or row[0].strip() == "":
                    continue  # ligne vide

                pays = row[0].strip() or "Allemagne"                  # col 0
                annee_reference = int(row[1])                         # col 1
                source_officielle = row[2].strip() or "DESTATIS"      # col 2
                sexe = row[3].strip()                                 # col 3 ("Femme"/"Homme")
                age = int(row[4])                                     # col 4
                ev_restante_str = row[5].replace(",", ".")            # col 5
                esperance_vie_restante = float(ev_restante_str)

                date_pub_str = row[6].strip() if len(row) > 6 else ""
                date_publication_source = datetime.date(int(annee_reference), 1, 1)
                if date_pub_str:
                    # format 21.08.2024
                    jour, mois, an = date_pub_str.split(".")
                    date_publication_source = datetime.date(int(an), int(mois), int(jour))

                actif_str = row[7].strip().lower() if len(row) > 7 else "oui"
                actif = actif_str in ("oui", "yes", "true", "1")

                obj, created_flag = TableEsperanceVie.objects.update_or_create(
                    pays=pays,
                    annee_reference=annee_reference,
                    sexe=sexe,
                    age=age,
                    defaults={
                        "esperance_vie_restante": esperance_vie_restante,
                        "source_officielle": source_officielle,
                        "date_publication_source": date_publication_source,
                        "date_import": timezone.now().date(),
                        "actif": actif,
                    },
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1

        self.message_user(
            request,
            f"Import DE 2023 terminé : {created} créés, {updated} mis à jour.",
            level=messages.INFO,
        )
        return redirect("admin:core_tableesperancevie_changelist")

                   
     # méthode import_lu_2023 ici ...
    def has_add_permission(self, request):
        # empêche l'ajout manuel, cahe le bouton "Add" dans l'admin
        return False
    
    def has_delete_permission(self, request, obj = None):
        # empêche la suppression, cache les cases à cocher et le bouton "Delete"
        return False