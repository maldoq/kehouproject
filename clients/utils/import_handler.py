import pandas as pd
from datetime import date
from clients.models import Client, FluxMensuel, Versement
from clients.utils.kis_algorithm import calculer_et_sauvegarder_kis


def import_from_file(file_obj):
    """
    Importe des clients depuis un fichier CSV ou Excel.
    Retourne (nb_importes, nb_erreurs, erreurs_detail)
    """
    filename = file_obj.name.lower()
    if filename.endswith('.csv'):
        df = pd.read_csv(file_obj)
    elif filename.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_obj)
    else:
        raise ValueError("Format non supporté. Utilisez CSV ou Excel.")

    required_cols = ['nom', 'prenom', 'activite', 'anciennete_annees',
                     'nb_categories', 'freq_stock_par_an']
    flux_cols = [f'flux_m{i}' for i in range(1, 13)]
    versement_cols = [f'versement_m{i}' for i in range(1, 13)]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes : {', '.join(missing)}")

    nb_importes = 0
    nb_erreurs = 0
    erreurs = []

    for idx, row in df.iterrows():
        try:
            client = Client.objects.create(
                nom=str(row.get('nom', '')).strip(),
                prenom=str(row.get('prenom', '')).strip(),
                activite=str(row.get('activite', '')).strip(),
                anciennete_annees=int(row.get('anciennete_annees', 1)),
                nb_categories=int(row.get('nb_categories', 1)),
                freq_stock_par_an=int(row.get('freq_stock_par_an', 12)),
                telephone=str(row.get('telephone', '')).strip() if 'telephone' in row else '',
            )

            today = date.today()
            base_year = today.year - 1

            for i, col in enumerate(flux_cols, 1):
                if col in df.columns:
                    mois_date = date(base_year, i, 1) if i <= 12 else date(today.year, i - 12, 1)
                    FluxMensuel.objects.create(
                        client=client,
                        mois=mois_date,
                        montant_entrant=int(float(row.get(col, 0)))
                    )

            for i, col in enumerate(versement_cols, 1):
                if col in df.columns:
                    mois_date = date(base_year, i, 1) if i <= 12 else date(today.year, i - 12, 1)
                    Versement.objects.create(
                        client=client,
                        mois=mois_date,
                        montant=int(float(row.get(col, 0)))
                    )

            calculer_et_sauvegarder_kis(client)
            nb_importes += 1

        except Exception as e:
            nb_erreurs += 1
            erreurs.append(f"Ligne {idx + 2}: {str(e)}")

    return nb_importes, nb_erreurs, erreurs
