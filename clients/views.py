from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Avg, Sum
from django.views.decorators.http import require_POST, require_http_methods
from datetime import date, datetime
import json

from .models import Client, FluxMensuel, Versement, KISScore
from .utils.kis_algorithm import calculer_et_sauvegarder_kis, MENSUALITE
from .utils.import_handler import import_from_file
from .utils.whatsapp_mock import send_rappel_whatsapp, send_rappel_groupe


# ─── DASHBOARD ───────────────────────────────────────────────────────────────

def dashboard(request):
    today = date.today()
    total_clients = Client.objects.count()
    clients_ce_mois = Client.objects.filter(
        date_inscription__year=today.year,
        date_inscription__month=today.month
    ).count()
    clients_cette_annee = Client.objects.filter(date_inscription__year=today.year).count()

    # Répartition profils KIS
    profils = KISScore.objects.values('profil').annotate(count=Count('profil'))
    profil_data = {p['profil']: p['count'] for p in profils}

    # Taux d'acceptation
    acceptes = KISScore.objects.filter(
        profil__in=['Financable', 'Tres fiable', 'Premium']
    ).count()
    total_scores = KISScore.objects.count()
    taux_acceptation = round((acceptes / total_scores * 100) if total_scores > 0 else 0, 1)

    # Courbe versements par mois (12 derniers mois)
    versements_par_mois = []
    flux_moy_par_mois = []
    mois_labels = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        mois_date = date(y, m, 1)
        label = mois_date.strftime('%b %Y')
        mois_labels.append(label)
        nb_versements = Versement.objects.filter(mois=mois_date).count()
        versements_par_mois.append(nb_versements)
        flux_moy = FluxMensuel.objects.filter(mois=mois_date).aggregate(
            moy=Avg('montant_entrant'))['moy'] or 0
        flux_moy_par_mois.append(float(flux_moy))

    # Clients en retard
    mois_courant = date(today.year, today.month, 1)
    clients_en_retard = []
    for client in Client.objects.all():
        versement = Versement.objects.filter(client=client, mois=mois_courant).first()
        if versement is None or versement.montant < MENSUALITE * 0.9:
            clients_en_retard.append(client)

    context = {
        'total_clients': total_clients,
        'clients_ce_mois': clients_ce_mois,
        'clients_cette_annee': clients_cette_annee,
        'taux_acceptation': taux_acceptation,
        'profil_data': json.dumps(profil_data),
        'mois_labels': json.dumps(mois_labels),
        'versements_par_mois': json.dumps(versements_par_mois),
        'flux_moy_par_mois': json.dumps(flux_moy_par_mois),
        'nb_retards': len(clients_en_retard),
        'acceptes': acceptes,
        'total_scores': total_scores,
    }
    return render(request, 'clients/dashboard.html', context)


# ─── LISTE CLIENTS ────────────────────────────────────────────────────────────

def client_list(request):
    query = request.GET.get('q', '')
    profil_filter = request.GET.get('profil', '')

    clients = Client.objects.select_related('kisscore').all()
    if query:
        clients = clients.filter(nom__icontains=query) | clients.filter(prenom__icontains=query) | clients.filter(activite__icontains=query)
    if profil_filter:
        clients = clients.filter(kisscore__profil=profil_filter)

    profils_disponibles = ['Premium', 'Tres fiable', 'Financable', 'Sous surveillance', 'Risque eleve', 'Refus']
    return render(request, 'clients/client_list.html', {
        'clients': clients,
        'query': query,
        'profil_filter': profil_filter,
        'profils_disponibles': profils_disponibles,
    })


# ─── DÉTAIL CLIENT ────────────────────────────────────────────────────────────

def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    flux_qs = FluxMensuel.objects.filter(client=client).order_by('mois')
    versements_qs = Versement.objects.filter(client=client).order_by('mois')
    kis_score = client.get_kis_score()

    flux_labels = [f.mois.strftime('%b %Y') for f in flux_qs]
    flux_data = [float(f.montant_entrant) for f in flux_qs]
    versements_labels = [v.mois.strftime('%b %Y') for v in versements_qs]
    versements_data = [float(v.montant) for v in versements_qs]

    context = {
        'client': client,
        'kis_score': kis_score,
        'flux_labels': json.dumps(flux_labels),
        'flux_data': json.dumps(flux_data),
        'versements_labels': json.dumps(versements_labels),
        'versements_data': json.dumps(versements_data),
        'flux_qs': flux_qs,
        'versements_qs': versements_qs,
        'MENSUALITE': MENSUALITE,
    }
    return render(request, 'clients/client_detail.html', context)


# ─── CRÉER CLIENT ─────────────────────────────────────────────────────────────

def client_create(request):
    if request.method == 'POST':
        try:
            client = Client.objects.create(
                nom=request.POST.get('nom', '').strip(),
                prenom=request.POST.get('prenom', '').strip(),
                activite=request.POST.get('activite', '').strip(),
                anciennete_annees=int(request.POST.get('anciennete_annees', 1)),
                nb_categories=int(request.POST.get('nb_categories', 1)),
                freq_stock_par_an=int(request.POST.get('freq_stock_par_an', 12)),
                telephone=request.POST.get('telephone', '').strip(),
            )
            messages.success(request, f"Client {client} créé avec succès. Vous pouvez maintenant ajouter ses flux et versements mensuels.")
            return redirect('client_detail', pk=client.pk)
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    return render(request, 'clients/client_create.html')

# ─── Ajouter versement et flux ─────────────────────────────────────────────

@require_http_methods(["POST"])
def ajouter_flux(request, pk):
    client = get_object_or_404(Client, pk=pk)
    mois = request.POST.get('mois')
    montant = request.POST.get('montant')
    try:
        mois_date = datetime.strptime(mois, '%Y-%m').date()
        mois_date = date(mois_date.year, mois_date.month, 1)
        flux, created = FluxMensuel.objects.update_or_create(
            client=client,
            mois=mois_date,
            defaults={'montant_entrant': int(float(montant))}
        )
        calculer_et_sauvegarder_kis(client)
        messages.success(request, f"Flut entrant pour {mois_date.strftime('%B %Y')} enregistré.")
    except Exception as e:
        messages.error(request, f"Erreur : {e}")
    return redirect('client_detail', pk=client.pk)

@require_http_methods(["POST"])
def ajouter_versement(request, pk):
    client = get_object_or_404(Client, pk=pk)
    mois = request.POST.get('mois')
    montant = request.POST.get('montant')
    try:
        mois_date = datetime.strptime(mois, '%Y-%m').date()
        mois_date = date(mois_date.year, mois_date.month, 1)
        versement, created = Versement.objects.update_or_create(
            client=client,
            mois=mois_date,
            defaults={'montant': int(float(montant))}
        )
        calculer_et_sauvegarder_kis(client)
        messages.success(request, f"Versement pour {mois_date.strftime('%B %Y')} enregistré.")
    except Exception as e:
        messages.error(request, f"Erreur : {e}")
    return redirect('client_detail', pk=client.pk)

# ─── IMPORT ───────────────────────────────────────────────────────────────────

def import_clients(request):
    if request.method == 'POST' and request.FILES.get('fichier'):
        fichier = request.FILES['fichier']
        try:
            nb_ok, nb_err, erreurs = import_from_file(fichier)
            if nb_ok > 0:
                messages.success(request, f"{nb_ok} client(s) importé(s) avec succès.")
            if nb_err > 0:
                messages.warning(request, f"{nb_err} erreur(s) lors de l'import.")
                for err in erreurs[:5]:
                    messages.error(request, err)
        except Exception as e:
            messages.error(request, f"Erreur d'import : {e}")
        return redirect('client_list')

    return render(request, 'clients/import_clients.html')


# ─── RAPPELS ─────────────────────────────────────────────────────────────────

def rappels(request):
    today = date.today()
    mois_courant = date(today.year, today.month, 1)

    clients_retard = []
    for client in Client.objects.all():
        versement = Versement.objects.filter(client=client, mois=mois_courant).first()
        if versement is None or versement.montant < MENSUALITE * 0.9:
            montant_verse = float(versement.montant) if versement else 0
            clients_retard.append({
                'client': client,
                'montant_verse': montant_verse,
                'manque': max(0, MENSUALITE - montant_verse),
            })

    return render(request, 'clients/rappels.html', {
        'clients_retard': clients_retard,
        'MENSUALITE': MENSUALITE,
        'mois_courant': mois_courant,
    })


@require_POST
def envoyer_rappel(request, pk):
    client = get_object_or_404(Client, pk=pk)
    success = send_rappel_whatsapp(client)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': success, 'client': str(client)})
    messages.success(request, f"Rappel envoyé à {client}.")
    return redirect('rappels')


@require_POST
def envoyer_rappel_groupe(request):
    client_ids = request.POST.getlist('client_ids')
    clients = Client.objects.filter(pk__in=client_ids)
    resultats = send_rappel_groupe(clients)
    messages.success(request, f"Rappels envoyés à {len(resultats)} client(s).")
    return redirect('rappels')


# ─── ENREGISTREMENT MENSUALITÉ ────────────────────────────────────────────────

def enregistrement_mensualite(request):
    if request.method == 'POST':
        client_id = request.POST.get('client_id')
        mois_str = request.POST.get('mois')
        montant = request.POST.get('montant')

        try:
            client = Client.objects.get(pk=client_id)
            mois_date = datetime.strptime(mois_str, '%Y-%m').date()
            mois_date = date(mois_date.year, mois_date.month, 1)

            versement, created = Versement.objects.update_or_create(
                client=client,
                mois=mois_date,
                defaults={'montant': int(float(montant))}
            )
            calculer_et_sauvegarder_kis(client)
            action = "enregistré" if created else "mis à jour"
            messages.success(request, f"Versement {action} pour {client}. Score KIS recalculé.")
            return redirect('enregistrement_mensualite')

        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    clients = Client.objects.all().order_by('nom')
    return render(request, 'clients/enregistrement_mensualite.html', {
        'clients': clients,
        'today': date.today(),
    })


# ─── API JSON ─────────────────────────────────────────────────────────────────

def api_clients(request):
    clients = Client.objects.select_related('kisscore').all()
    data = []
    for c in clients:
        ks = c.get_kis_score()
        data.append({
            'id': c.pk,
            'nom': str(c),
            'activite': c.activite,
            'anciennete': c.anciennete_annees,
            'kis': ks.kis if ks else None,
            'profil': ks.profil if ks else None,
        })
    return JsonResponse({'clients': data})


def api_versements(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        client = get_object_or_404(Client, pk=data['client_id'])
        mois_date = datetime.strptime(data['mois'], '%Y-%m-%d').date()
        v, _ = Versement.objects.update_or_create(
            client=client, mois=mois_date,
            defaults={'montant': data['montant']}
        )
        calculer_et_sauvegarder_kis(client)
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'POST only'}, status=405)
