import numpy as np

MENSUALITE = 563332


def score_capacite(ratio):
    if ratio > 5: return 100
    if ratio >= 4: return 90
    if ratio >= 3: return 80
    if ratio >= 2: return 60
    if ratio >= 1: return 40
    return 0


def score_stabilite(cv):
    if cv < 0.20: return 100
    if cv < 0.40: return 80
    if cv < 0.60: return 60
    return 30


def score_anciennete(ans):
    if ans > 10: return 100
    if ans >= 5: return 80
    if ans >= 2: return 60
    return 30


def score_rotation(freq_stock_par_an):
    if freq_stock_par_an >= 52: return 100
    if freq_stock_par_an >= 26: return 80
    if freq_stock_par_an >= 12: return 60
    return 30


def score_diversification(nb_categories):
    if nb_categories > 5: return 100
    if nb_categories >= 3: return 80
    if nb_categories == 2: return 60
    return 40


def ponctualite_from_versement(versement_montant):
    ratio = versement_montant / MENSUALITE
    if ratio >= 1.0:
        return 90
    elif ratio >= 0.9:
        return 70
    elif ratio >= 0.7:
        return 40
    else:
        return 0


def bonus_epargne_from_versement(versement_montant):
    if versement_montant > MENSUALITE:
        bonus = (versement_montant / MENSUALITE) * 100
        return min(bonus, 120)
    return 0


def calcul_discipline(versements_mensuels):
    scores_ponctualite = [ponctualite_from_versement(v) for v in versements_mensuels]
    bonus_mois = [bonus_epargne_from_versement(v) for v in versements_mensuels]
    discipline_moy = np.mean([p + b for p, b in zip(scores_ponctualite, bonus_mois)]) / 2
    return min(discipline_moy, 100.0)


def calcul_flux(flux_mensuels):
    flux_arr = [float(f) for f in flux_mensuels]
    flux_moy = np.mean(flux_arr)
    ratio = flux_moy / MENSUALITE
    capacite = score_capacite(ratio)

    ecart_type = np.std(flux_arr, ddof=1) if len(flux_arr) > 1 else 0
    cv = ecart_type / flux_moy if flux_moy > 0 else 999
    stabilite = score_stabilite(cv)

    seuil_pic = flux_moy * 1.5
    nb_pics = sum(1 for f in flux_arr if f > seuil_pic)
    bonus_pic = 10 if nb_pics >= 3 else 0

    flux_score = 0.6 * capacite + 0.4 * stabilite + bonus_pic
    return min(flux_score, 100.0)


def calcul_resilience(anciennete, freq_stock, nb_categories):
    ancien_score = score_anciennete(anciennete)
    rot_score = score_rotation(freq_stock)
    divers_score = score_diversification(nb_categories)
    resilience = 0.4 * ancien_score + 0.3 * rot_score + 0.3 * divers_score
    return resilience


def profil_kis(kis):
    if kis >= 90: return "Premium"
    if kis >= 80: return "Tres fiable"
    if kis >= 70: return "Financable"
    if kis >= 60: return "Sous surveillance"
    if kis >= 50: return "Risque eleve"
    return "Refus"


def calculer_et_sauvegarder_kis(client):
    from clients.models import FluxMensuel, Versement, KISScore

    flux_qs = FluxMensuel.objects.filter(client=client).order_by('mois')
    versement_qs = Versement.objects.filter(client=client).order_by('mois')

    flux_mensuels = [float(f.montant_entrant) for f in flux_qs]
    versements_mensuels = [float(v.montant) for v in versement_qs]

    if len(flux_mensuels) < 1 or len(versements_mensuels) < 1:
        return None

    # Pad to 12 if needed
    while len(flux_mensuels) < 12:
        flux_mensuels.append(0)
    while len(versements_mensuels) < 12:
        versements_mensuels.append(0)

    discipline = calcul_discipline(versements_mensuels[:12])
    flux_score = calcul_flux(flux_mensuels[:12])
    resilience = calcul_resilience(
        client.anciennete_annees,
        client.freq_stock_par_an,
        client.nb_categories
    )
    kis = 0.4 * discipline + 0.35 * flux_score + 0.25 * resilience
    profil = profil_kis(kis)

    score_obj, _ = KISScore.objects.update_or_create(
        client=client,
        defaults={
            'discipline': round(discipline, 2),
            'flux_score': round(flux_score, 2),
            'resilience': round(resilience, 2),
            'kis': round(kis, 2),
            'profil': profil,
        }
    )
    return score_obj
