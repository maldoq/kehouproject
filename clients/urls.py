from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('clients/', views.client_list, name='client_list'),
    path('clients/nouveau/', views.client_create, name='client_create'),
    path('clients/importer/', views.import_clients, name='import_clients'),
    path('clients/<int:pk>/', views.client_detail, name='client_detail'),
    path('rappels/', views.rappels, name='rappels'),
    path('rappels/envoyer/<int:pk>/', views.envoyer_rappel, name='envoyer_rappel'),
    path('rappels/groupe/', views.envoyer_rappel_groupe, name='envoyer_rappel_groupe'),
    path('mensualites/', views.enregistrement_mensualite, name='enregistrement_mensualite'),
    path('api/clients/', views.api_clients, name='api_clients'),
    path('api/versements/', views.api_versements, name='api_versements'),
    path('clients/<int:pk>/flux/ajouter/', views.ajouter_flux, name='ajouter_flux'),
    path('clients/<int:pk>/versement/ajouter/', views.ajouter_versement, name='ajouter_versement'),
]
