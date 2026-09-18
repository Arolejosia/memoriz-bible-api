"""
Service d'envoi de courriel via l'API HTTP de Resend.
Remplace SMTP (bloqué par Render) et ZeptoMail (config trop capricieuse).

Prérequis :
1. Crée un compte sur https://resend.com (gratuit, 3000 emails/mois, 100/jour)
2. Dans Resend > Domains, ajoute myezerdigital.ca
3. Resend affiche 3 enregistrements DNS (SPF, DKIM, et parfois un DMARC recommandé) —
   ajoute-les chez ton fournisseur DNS, la vérification est généralement rapide (~qqs minutes)
4. Une fois le domaine "Verified" dans Resend, va dans API Keys > Create API Key
5. Mets cette clé dans la variable d'environnement RESEND_API_KEY sur Render
"""

import os
import requests

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_API_KEY = os.environ["RESEND_API_KEY"]

ZOHO_SENDER_EMAIL = os.environ["ZOHO_SENDER_EMAIL"]  # ex: contact@myezerdigital.ca
ZOHO_SENDER_NAME = "L'équipe MemorizBible"


def send_verification_email(to_email: str, verification_link: str, display_name: str, lang: str = "fr") -> None:
    """
    Envoie un courriel de vérification personnalisé via l'API Resend.

    to_email: adresse du destinataire
    verification_link: lien généré par Firebase Admin (auth.generate_email_verification_link)
    display_name: nom affiché de l'utilisateur (peut être vide)
    lang: "fr" ou "en"
    """
    subject, html_body, text_body = _build_content(verification_link, display_name, lang)
    _send_via_resend(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)


def _send_via_resend(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    payload = {
        "from": f"{ZOHO_SENDER_NAME} <{ZOHO_SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(RESEND_API_URL, json=payload, headers=headers, timeout=15)

    if response.status_code >= 300:
        # On remonte le détail exact retourné par Resend pour faciliter le debug
        raise Exception(f"Resend error {response.status_code}: {response.text}")


def _build_content(link: str, name: str, lang: str) -> tuple[str, str, str]:
    greeting_name = name if name else ("ami lecteur" if lang == "fr" else "there")

    if lang == "fr":
        subject = "Confirme ton compte MemorizBible 📖"
        text_body = (
            f"Bonjour {greeting_name},\n\n"
            f"Merci de t'être inscrit sur MemorizBible !\n\n"
            f"Clique sur ce lien pour confirmer ton adresse courriel :\n{link}\n\n"
            f"Si tu n'as pas créé de compte, ignore simplement ce message.\n\n"
            f"À bientôt,\nL'équipe MemorizBible"
        )
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
          <h2 style="color:#1E40D0;">Bienvenue sur MemorizBible 📖</h2>
          <p>Bonjour {greeting_name},</p>
          <p>Merci de t'être inscrit ! Clique sur le bouton ci-dessous pour confirmer ton adresse courriel :</p>
          <p style="text-align:center; margin: 24px 0;">
            <a href="{link}" style="background:#1E40D0; color:white; padding:12px 24px;
               border-radius:24px; text-decoration:none; font-weight:bold;">
               Confirmer mon adresse
            </a>
          </p>
          <p style="font-size:12px; color:#888;">
            Si le bouton ne fonctionne pas, copie ce lien dans ton navigateur :<br>
            <a href="{link}">{link}</a>
          </p>
          <p style="font-size:12px; color:#888;">Si tu n'as pas créé de compte, ignore simplement ce message.</p>
        </div>
        """
    else:
        subject = "Confirm your MemorizBible account 📖"
        text_body = (
            f"Hi {greeting_name},\n\n"
            f"Thanks for signing up for MemorizBible!\n\n"
            f"Click this link to verify your email address:\n{link}\n\n"
            f"If you didn't create an account, you can safely ignore this email.\n\n"
            f"Best,\nThe MemorizBible team"
        )
        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
          <h2 style="color:#1E40D0;">Welcome to MemorizBible 📖</h2>
          <p>Hi {greeting_name},</p>
          <p>Thanks for signing up! Click the button below to verify your email address:</p>
          <p style="text-align:center; margin: 24px 0;">
            <a href="{link}" style="background:#1E40D0; color:white; padding:12px 24px;
               border-radius:24px; text-decoration:none; font-weight:bold;">
               Verify my email
            </a>
          </p>
          <p style="font-size:12px; color:#888;">
            If the button doesn't work, copy this link into your browser:<br>
            <a href="{link}">{link}</a>
          </p>
          <p style="font-size:12px; color:#888;">If you didn't create an account, you can safely ignore this email.</p>
        </div>
        """
    return subject, html_body, text_body
