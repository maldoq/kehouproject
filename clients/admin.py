from django.contrib import admin
from .models import Client, FluxMensuel, Versement, KISScore


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['nom', 'prenom', 'activite', 'anciennete_annees', 'date_inscription']
    search_fields = ['nom', 'prenom', 'activite']


@admin.register(KISScore)
class KISScoreAdmin(admin.ModelAdmin):
    list_display = ['client', 'kis', 'profil', 'discipline', 'flux_score', 'resilience', 'date_calcul']
    list_filter = ['profil']


admin.site.register(FluxMensuel)
admin.site.register(Versement)
