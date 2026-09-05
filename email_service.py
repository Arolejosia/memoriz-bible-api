"""
Service d'envoi de courriel via Zoho SMTP.
Remplace l'envoi automatique de Firebase pour la vérification d'email,
afin de contrôler le contenu et éviter le domaine partagé firebaseapp.com
(qui est actuellement bloqué en édition et sujet à un mauvais taux de délivrabilité).
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Configuration Zoho (à mettre dans les variables d'environnement sur Render) ---
ZOHO_SMTP_HOST = "smtp.zoho.com"
ZOHO_SMTP_PORT = 587
ZOHO_SENDER_EMAIL = os.environ["ZOHO_SENDER_EMAIL"]      # ex: noreply@myezerdigital.ca
ZOHO_SENDER_PASSWORD = os.environ["ZOHO_SENDER_PASSWORD"]  # mot de passe d'application Zoho
ZOHO_SENDER_NAME = "L'équipe MemorizBible"


def send_verification_email(to_email: str, verification_link: str, display_name: str, lang: str = "fr") -> None:
    """
    Envoie un courriel de vérification personnalisé via Zoho SMTP.

    to_email: adresse du destinataire
    verification_link: lien généré par Firebase Admin (auth.generate_email_verification_link)
    display_name: nom affiché de l'utilisateur (peut être vide)
    lang: "fr" ou "en"
    """
    subject, html_body, text_body = _build_content(verification_link, display_name, lang)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{ZOHO_SENDER_NAME} <{ZOHO_SENDER_EMAIL}>"
    msg["To"] = to_email

    # Toujours inclure une version texte brut ET html — améliore la délivrabilité
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(ZOHO_SMTP_HOST, ZOHO_SMTP_PORT) as server:
        server.starttls()
        server.login(ZOHO_SENDER_EMAIL, ZOHO_SENDER_PASSWORD)
        server.sendmail(ZOHO_SENDER_EMAIL, [to_email], msg.as_string())


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
