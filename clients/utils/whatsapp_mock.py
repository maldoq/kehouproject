import logging
import pywhatkit as kit
import threading

logger = logging.getLogger('kehou')

def send_whatsapp(phone_number, message, client_name=""):
    """Envoie un message WhatsApp en asynchrone (instantané)."""
    # Nettoyer et formater le numéro avec l'indicatif +225
    cleaned = phone_number.replace(' ', '').replace('-', '').lstrip('+')
    if not cleaned.startswith('225'):
        cleaned = '225' + cleaned
    full_number = '+' + cleaned

    thread = threading.Thread(
        target=_send_whatsapp_thread,
        args=(full_number, message, client_name),
        daemon=True
    )
    thread.start()
    return True

def _send_whatsapp_thread(phone_number, message, client_name):
    try:
        # Envoi immédiat, ferme l'onglet après 20 secondes
        kit.sendwhatmsg_instantly(phone_number, message, wait_time=20, tab_close=True)
        logger.info(f"[WhatsApp] Message envoyé à {phone_number} ({client_name})")
        print(f"📱 WhatsApp → {phone_number} ({client_name})")
    except Exception as e:
        logger.error(f"Erreur pywhatkit : {e}")
        print(f"❌ Erreur d'envoi à {phone_number} : {e}")

def send_rappel_whatsapp(client):
    MENSUALITE = 563_332
    phone = client.telephone
    if not phone:
        logger.warning(f"Client {client} sans numéro de téléphone")
        return False
    message = (
        f"*KEHOU Property* - Rappel de paiement\n\n"
        f"Bonjour {client.prenom} {client.nom},\n\n"
        f"Nous vous rappelons que votre mensualité de {MENSUALITE:,} FCFA "
        f"est due ce mois-ci dans le cadre de votre financement immobilier.\n\n"
        f"Merci de régulariser votre situation.\n\n"
        f"— L'équipe KEHOU Property"
    )
    return send_whatsapp(phone, message, str(client))

def send_rappel_groupe(clients):
    resultats = []
    for client in clients:
        success = send_rappel_whatsapp(client)
        resultats.append({'client': str(client), 'success': success})
    return resultats