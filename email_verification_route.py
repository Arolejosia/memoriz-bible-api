"""
Version TEMPORAIRE de debug — à remettre comme avant une fois le bug trouvé.
Ajoute juste un traceback complet dans le message d'erreur retourné,
pour voir directement dans Flutter (ou Postman/navigateur) ce qui plante,
sans dépendre des logs Render.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import firebase_admin
from firebase_admin import auth, credentials
import os
import traceback  # ← ajouté

from email_service import send_verification_email

router = APIRouter()

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
    lang: str = "fr"


@router.post("/api/send-verification-email")
def send_verification(payload: VerificationRequest):
    try:
        link = auth.generate_email_verification_link(payload.email)
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        # ← on renvoie le traceback complet dans le detail, temporairement
        tb = traceback.format_exc()
        print(tb)  # apparaîtra aussi dans les logs Render
        raise HTTPException(status_code=500, detail=f"Error generating link: {e}\n\n{tb}")

    try:
        send_verification_email(
            to_email=payload.email,
            verification_link=link,
            display_name=payload.display_name,
            lang=payload.lang,
        )
    except Exception as e:
        tb = traceback.format_exc()
        print(tb)  # apparaîtra aussi dans les logs Render
        raise HTTPException(status_code=500, detail=f"Error sending email: {e}\n\n{tb}")

    return {"status": "sent"}
