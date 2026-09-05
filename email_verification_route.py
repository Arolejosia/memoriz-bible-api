"""
Route FastAPI : génère un lien de vérification Firebase et l'envoie
via Zoho SMTP plutôt que via l'envoi automatique de Firebase.

À monter dans ton app FastAPI existante (main.py) avec :
    from email_verification_route import router as email_router
    app.include_router(email_router)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import firebase_admin
from firebase_admin import auth, credentials
import os

from email_service import send_verification_email

router = APIRouter()

# --- Initialisation Firebase Admin (une seule fois au démarrage du serveur) ---
# Le fichier de clé de service doit être stocké de façon sécurisée
# (variable d'environnement contenant le JSON, ou secret file sur Render),
# jamais commité dans le repo.
if not firebase_admin._apps:
    cred = credentials.Certificate({
        "type": "service_account",
        "project_id": os.environ["FIREBASE_PROJECT_ID"],
        "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
        "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
        "token_uri": "https://oauth2.googleapis.com/token",
    })
    firebase_admin.initialize_app(cred)


class VerificationRequest(BaseModel):
    email: EmailStr
    display_name: str = ""
    lang: str = "fr"  # "fr" ou "en"


@router.post("/api/send-verification-email")
def send_verification(payload: VerificationRequest):
    """
    Appelé depuis l'app Flutter juste après la création du compte,
    à la place de user.sendEmailVerification().
    """
    try:
        # Génère le lien officiel Firebase (même mécanisme de vérification,
        # juste envoyé par nous plutôt que par Firebase directement)
        link = auth.generate_email_verification_link(payload.email)
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating link: {e}")

    try:
        send_verification_email(
            to_email=payload.email,
            verification_link=link,
            display_name=payload.display_name,
            lang=payload.lang,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending email: {e}")

    return {"status": "sent"}
