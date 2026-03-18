from django.db import models
from django.utils import timezone

from decimal import Decimal
from .finance_utils import calcul_age, get_esperance_vie

class Proprietaire(models.Model):
    PAYS_CHOICES = [
        ("Luxembourg", "Luxembourg"),
        ("Allemagne", "Allemagne"),
    ]

    nom = models.CharField("Nom", max_length=100)
    prenom = models.CharField("Prénom", max_length=100)

    # Bloc adresse
    rue_numero = models.CharField("Rue et numéro", max_length=255, blank=True)
    code_postal = models.CharField("Code postal", max_length=6, blank=True)
    ville = models.CharField("Ville", max_length=100, blank=True)
    canton_etat = models.CharField("Canton/État fédéral", max_length=100, blank=True)

    PAYS_CHOICES = [
        ("Luxembourg", "Luxembourg"),
        ("Allemagne", "Allemagne"),
    ]
    pays = models.CharField("Pays", max_length=20, choices=PAYS_CHOICES, default="Luxembourg")

    date_naissance = models.DateField()
    nationalite = models.CharField(max_length=100, blank=True)
    sexe = models.CharField(
        max_length=1,
        choices=[("M", "Homme"), ("F", "Femme")],
    )
    telephone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    age_actuel = models.IntegerField(null=True, blank=True)
    esperance_vie = models.FloatField(null=True, blank=True)

    def mettre_a_jour_age_et_ev(self):
        if not self.date_naissance:
            return
        
        today = timezone.now().date()
        age = calcul_age(self.date_naissance, today)
        self.age_actuel = age

        # calcul de l'espérance de vie sur base de la table
        if age is not None:
            # on utilise le code pays LU/DE srocké sur le propriétaire
            ev = get_esperance_vie(pays=self.pays, sexe=self.sexe, age=age)
            self.esperance_vie = ev
           
    def save(self, *args, **kwargs):
        self.mettre_a_jour_age_et_ev()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.prenom} {self.nom}"

class Bien(models.Model):
    TYPE_BIEN_CHOICES = [
        ("RESIDENTIEL", "Résidentiel"),
        ("COMMERCE", "Commerce"),
        ("BUREAU", "Bureau"),
        ("HOTEL", "Hôtel"),
        ("HALL", "Hall"),
    ]

    CATEGORIE_LOGEMENT_CHOICES = [
        ("MAISON_UNI", "Maison unifamiliale"),
        ("MAISON_BI", "Maison bifamiliale"),
        ("APPART", "Appartement"),
        ("AUTRE", "Autre"),
    ]

    type_bien = models.CharField(
        max_length=20,
        choices=TYPE_BIEN_CHOICES,
    )
    categorie_logement = models.CharField(
        max_length=20,
        choices=CATEGORIE_LOGEMENT_CHOICES,
        blank=True,
    )
    adresse = models.CharField(max_length=255)
    code_postal = models.CharField(max_length=20, blank=True)
    ville = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=50, default="Luxembourg")
    surface_habitable = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    surface_utile = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    superficie_terrain = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # donnees_cadastrales = models.TextField(blank=True)
    annee_construction = models.IntegerField(null=True, blank=True)
    etat = models.CharField(max_length=100, blank=True)
    loyer_actuel = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valeur_locative = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valeur_venale_estimee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valeur_reelle = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cpe = models.CharField(max_length=100, blank=True)
    charges_locataire = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    investissements_travaux_prevus = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    situation_pag_pap = models.TextField(blank=True)
    syndic = models.CharField(max_length=255, blank=True)
    proprietaires = models.ManyToManyField(Proprietaire, related_name="biens", blank=True)

    def __str__(self):
        return f"{self.get_type_bien_display()} - {self.adresse}"

class ExtraitCadastral(models.Model):
    PAYS_CHOICES = [
        ("LU", "Luxembourg"),
        ("DE", "Allemagne"),
    ]

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="extraits_cadastraux")
    pays = models.CharField(max_length=2, choices=PAYS_CHOICES, default="LU")

    commune = models.CharField(max_length=100, blank=True)
    section = models.CharField(max_length=100, blank=True)
    date_emission = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True)

    fichier = models.FileField(upload_to="extraits_cadastraux/", blank=True, null=True)
    remarque = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.get_pays_display()} – {self.commune} – {self.section} ({self.reference})"

class Parcelle(models.Model):
    extrait = models.ForeignKey(ExtraitCadastral, on_delete=models.CASCADE, related_name="parcelles")

    # Champs communs (LU / DE)
    numero_parcelle = models.CharField(max_length=50)          # No parcelle / Flurstück
    lieudit = models.CharField(max_length=100, blank=True)     # Lieudit / Strassenname
    nature = models.CharField(max_length=100, blank=True)      # Nature(s)
    occupation = models.CharField(max_length=100, blank=True)  # Occupation(s)

    # Spécifiques Luxembourg (d’après ton relevé)
    quote_part = models.CharField(max_length=20, blank=True)   # QP (ex. 1/2)
    contenance = models.CharField(max_length=20, blank=True)   # CT (ex. 22a26ca)
    revenu_bati_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)     # RBT
    revenu_non_bati_total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # RNBT

    commentaire = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.numero_parcelle} – {self.lieudit}"

class DossierViager(models.Model):
    class Meta:
        verbose_name = "Dossier de viager"
        verbose_name_plural = "Dossiers de viager"

    TYPE_VIAGER_CHOICES = [
        ("CLASSIQUE_OCCUPE", "Viager classique occupé"),
        ("CLASSIQUE_LIBRE", "Viager classique libre"),
        ("LONG_TERME", "Viager long terme"),
            ]

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="dossiers")
    type_viager = models.CharField(
        max_length=20,
        choices=TYPE_VIAGER_CHOICES,
    )
    date_creation = models.DateField(auto_now_add=True)
    description_interne = models.TextField(blank=True)

    parametres_pays = models.ForeignKey(
        "ParametresPays",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Paramètres standards du pays (taux, frais, etc.)",
    )
    date_signature = models.DateField(
        null=True,
        blank=True,
        help_text="Date de signature de l'acte de viager.",
    )
    age_signature = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Âge du crédirentier à la date de signature.",
    )
    esperance_vie_signature = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Espérance de vie restante (en années) à la date de signature.",
    )

    def __str__(self):
        return f"Dossier {self.id} - {self.bien} - {self.get_type_viager_display()}"


class ScenarioViager(models.Model):
    TYPE_SCENARIO_CHOICES = [
        ("CLASSIQUE", "Viager classique"),
        ("TEMPORAIRE", "Rente temporaire"),
        ("MIXTE", "Mixte (temporaire + viagère)"),
    ]

    STATUT_CHOICES = [
        ("EN_SUSPENS", "En suspens"),
        ("ACQUIS", "Acquis"),
        ("REFUS_VENDEUR", "Refus vendeur"),
        ("REFUS_ACQUEREUR", "Refus acquéreur"),
    ]

    dossier = models.ForeignKey(DossierViager, on_delete=models.CASCADE, related_name="scenarios")
    nom_scenario = models.CharField(max_length=100, blank=True)
    type_scenario = models.CharField(
        max_length=20,
        choices=TYPE_SCENARIO_CHOICES,
        default="CLASSIQUE",
    )
    bouquet_pourcent = models.DecimalField(max_digits=5, decimal_places=2)  # ex 0.20 pour 20 %
    bouquet_montant = models.DecimalField(max_digits=12, decimal_places=2)
    rente_viagere_mensuelle = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    duree_rente_temporaire_annees = models.IntegerField(null=True, blank=True)
    tri = models.DecimalField(max_digits=6, decimal_places=4, null=True, blank=True)
    van = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    investissement_initial = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    enveloppe_credirentier = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)
    cout_annuel_total = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True)

    respecte_plafond_60 = models.BooleanField(default=True)

    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default="EN_SUSPENS",
    )
    date_calcul = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nom_scenario or f"Scénario {self.id} du dossier {self.dossier_id}"


class ParametresPays(models.Model):
    PAYS_LU = "LU"
    PAYS_DE = "DE"

    PAYS_CHOICES = [
        (PAYS_LU, "Luxembourg"),
        (PAYS_DE, "Allemagne"),
    ]

    pays = models.CharField(max_length=2, choices=PAYS_CHOICES, unique=True)

    # B. Bien immeuble
    entretien_annuel_proprietaire = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.80")
    )  # % de la valeur
    frais_fixes_proprietaire = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.40")
    )  # % de la valeur
    appreciation_valeur_immo = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("2.00")
    )  # %/an

    # C. Débirentier
    taux_bce = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("2.15")
    )  # %
    majoration_risque = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("2.50")
    )  # points de %
    rendement_cible = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("4.65")
    )  # %

    # D. Frais administratifs
    frais_fis_annuel = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("0.60")
    )  # %
    frais_gm_annuel = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("0.75")
    )  # %
    frais_compte_bancaire = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("0.05")
    )  # %

    # E. Frais d'acquisition
    frais_agence = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("3.00")
    )  # %
    frais_notaire = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("7.50")
    )  # %
    ouverture_dossier_fis = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("2000.00")
    )  # EUR
    ouverture_dossier_gm = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("1000.00")
    )  # EUR

    class Meta:
        verbose_name = "Paramètres pays"
        verbose_name_plural = "Paramètres pays"

    def __str__(self):
        return f"Paramètres {self.get_pays_display()}"

class TableEsperanceVie(models.Model):
    PAYS_CHOICES = [
        ("Luxembourg", "Luxembourg"),
        ("Allemagne", "Allemagne"),
    ]

    SEXE_CHOICES = [
        ("Homme", "Homme"),
        ("Femme", "Femme"),
    ]

    # Identification de la table
    pays = models.CharField(
        max_length=20,
        choices=PAYS_CHOICES,
        help_text="Pays (Luxembourg, Allemagne).",
    )
    source_officielle = models.CharField(
        max_length=100,
        help_text="Exemple : STATEC, Destatis, etc.",
    )
    annee_reference = models.IntegerField(
        help_text="Année de référence de la table officielle (ex : 2023).",
    )

    # Ligne d'âge
    sexe = models.CharField(
        max_length=10,
        choices=SEXE_CHOICES,
        help_text="Sexe de la personne.",
    )
    age = models.PositiveIntegerField(
        help_text="Âge en années révolues (0 à 120).",
    )
    esperance_vie_restante = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Espérance de vie restante à cet âge (en années, ex : 23.45).",
    )

    # Métadonnées
    date_publication_source = models.DateField(
        help_text="Date de publication de la table par l'organisme officiel.",
    )
    date_import = models.DateTimeField(
        auto_now_add=True,
        help_text="Date de l'import dans ApexViager.",
    )
    actif = models.BooleanField(
        default=True,
        help_text="Cocher pour indiquer que cette table est active.",
    )

    # Espérance de vie du crédirentier au moment de la signature
    esperance_vie_signature = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Espérance de vie restante (en années) à la date de signature.",
    )
    age_signature = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Âge du crédirentier à la date de signature.",
    )
    date_signature = models.DateField(
        null=True,
        blank=True,
        help_text="Date de signature de l'acte de viager.",
    )

    class Meta:
        verbose_name = "Table d'espérance de vie"
        verbose_name_plural = "Tables d'espérance de vie"
        unique_together = ("pays", "annee_reference", "sexe", "age")

    def __str__(self):
        return (
            f"{self.get_pays_display()} - {self.annee_reference} - "
            f"{self.get_sexe_display()} - {self.age} ans"
        )
