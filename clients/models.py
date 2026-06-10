from django.db import models
from django.utils import timezone


class Client(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    activite = models.CharField(max_length=100)
    anciennete_annees = models.IntegerField()
    nb_categories = models.IntegerField()
    freq_stock_par_an = models.IntegerField(help_text="Nombre de réapprovisionnements par an")
    telephone = models.CharField(max_length=20, blank=True, null=True)
    date_inscription = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-date_inscription']

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    def get_kis_score(self):
        try:
            return self.kisscore
        except KISScore.DoesNotExist:
            return None

    def is_en_retard(self):
        from datetime import date
        MENSUALITE = 563332
        today = date.today()
        mois_courant = date(today.year, today.month, 1)
        versement = self.versement_set.filter(mois=mois_courant).first()
        if versement is None:
            return True
        return versement.montant < MENSUALITE * 0.9


class FluxMensuel(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    mois = models.DateField()
    montant_entrant = models.DecimalField(max_digits=12, decimal_places=0)

    class Meta:
        ordering = ['mois']
        unique_together = ['client', 'mois']

    def __str__(self):
        return f"{self.client} - {self.mois} - {self.montant_entrant}"


class Versement(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    mois = models.DateField()
    montant = models.DecimalField(max_digits=12, decimal_places=0)

    class Meta:
        ordering = ['mois']
        unique_together = ['client', 'mois']

    def __str__(self):
        return f"{self.client} - {self.mois} - {self.montant}"


class KISScore(models.Model):
    client = models.OneToOneField(Client, on_delete=models.CASCADE)
    discipline = models.FloatField()
    flux_score = models.FloatField()
    resilience = models.FloatField()
    kis = models.FloatField()
    profil = models.CharField(max_length=50)
    date_calcul = models.DateTimeField(auto_now=True)

    PROFIL_COLORS = {
        'Premium': '#FFD700',
        'Tres fiable': '#4CAF50',
        'Financable': '#2196F3',
        'Sous surveillance': '#FF9800',
        'Risque eleve': '#FF5722',
        'Refus': '#F44336',
    }

    PROFIL_ICONS = {
        'Premium': '⭐',
        'Tres fiable': '✅',
        'Financable': '💰',
        'Sous surveillance': '⚠️',
        'Risque eleve': '🔴',
        'Refus': '❌',
    }

    def get_color(self):
        return self.PROFIL_COLORS.get(self.profil, '#999')

    def get_icon(self):
        return self.PROFIL_ICONS.get(self.profil, '•')

    def __str__(self):
        return f"KIS {self.client}: {self.kis} ({self.profil})"
