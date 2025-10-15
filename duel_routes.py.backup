from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import random
import re
from typing import List, Optional

router = APIRouter()

# --- Chargement des données ---
try:
    with open("segond_1910.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        versets = raw_data.get("verses", [])
except (FileNotFoundError, json.JSONDecodeError):
    print("Erreur: Impossible de charger le fichier JSON.")
    versets = []

# --- Modèles de données ---
class BatchQcmRequest(BaseModel):
    reference: str
    niveau: str   # "facile", "moyen", "difficile"
    nombre: int
    mots_deja_utilises: Optional[List[str]] = None

class ReferenceRequest(BaseModel):
    reference: str
    niveau: str
    mots_deja_utilises: Optional[List[str]] = None

# --- Utils ---
def normalize_text(s: str) -> str:
    """Met en minuscule, retire les accents et la ponctuation."""
    s = s.lower().strip()
    replacements = {
        "á":"a","à":"a","â":"a","ä":"a",
        "é":"e","è":"e","ê":"e","ë":"e",
        "í":"i","î":"i","ï":"i",
        "ó":"o","ô":"o","ö":"o",
        "ú":"u","ù":"u","û":"u","ü":"u",
        "ç":"c",
    }
    for a, b in replacements.items():
        s = s.replace(a, b)
    import string
    return s.translate(str.maketrans('', '', string.punctuation))

def parse_reference(reference: str):
    """Analyse une référence biblique (ex: 'Jean 3:16-18')."""
    reference = reference.strip()
    numeros_versets = None
    if ":" in reference:
        partie_gauche, plage = reference.rsplit(":", 1)
        livre, chapitre_str = partie_gauche.rsplit(" ", 1)
        if "-" in plage:
            debut, fin = map(int, plage.split("-"))
            numeros_versets = list(range(debut, fin + 1))
        else:
            numeros_versets = [int(plage)]
    else:
        livre, chapitre_str = reference.rsplit(" ", 1)

    chapitre = int(chapitre_str)
    livre = livre.strip().capitalize()

    return livre, chapitre, numeros_versets

def get_versets(livre: str, chapitre: int, numeros: Optional[List[int]] = None):
    """Retourne une liste de versets correspondant à la référence."""
    if numeros:
        return [v for v in versets 
                if v.get("book_name", "").strip().lower() == livre.lower() 
                and v.get("chapter") == chapitre 
                and v.get("verse") in numeros]
    else:
        return [v for v in versets 
                if v.get("book_name", "").strip().lower() == livre.lower() 
                and v.get("chapter") == chapitre]

# --- Génération QCM ---
def jeu_qcm_single(data: ReferenceRequest):
    try:
        livre, chapitre, numeros = parse_reference(data.reference)
        versets_selectionnes = get_versets(livre, chapitre, numeros)

        if not versets_selectionnes:
            return {"error": "Aucun verset trouvé."}

        verset_question = random.choice(versets_selectionnes)
        mots_utilises = {normalize_text(mot) for mot in (data.mots_deja_utilises or [])}

        mots = verset_question["text"].split()
        mots_eligibles = {normalize_text(mot) for mot in mots if len(mot) > 3}
        mots_non_utilises = list(mots_eligibles - mots_utilises) or list(mots_eligibles)

        if not mots_non_utilises:
            return {"error": "Aucun mot disponible."}

        mot_correct = random.choice(mots_non_utilises)
        mot_a_retirer = next((mot for mot in mots if normalize_text(mot) == mot_correct), mot_correct)

        mauvais_mots = set()
        if data.niveau.lower() == "facile":
            pool = [v for v in versets if v.get("book_name") != verset_question.get("book_name")]
        elif data.niveau.lower() == "difficile":
            pool = [v for v in versets if v.get("book_name") == verset_question.get("book_name") 
                                         and v.get("chapter") == verset_question.get("chapter")]
        else:  # moyen
            pool = [v for v in versets if v.get("book_name") == verset_question.get("book_name")]

        random.shuffle(pool)
        while len(mauvais_mots) < 3 and pool:
            mots_option = pool.pop()['text'].split()
            mots_propres = {normalize_text(m) for m in mots_option if len(m) > 3}
            mots_propres.discard(mot_correct.lower())
            if mots_propres:
                mauvais_mots.add(random.choice(list(mots_propres)))

        while len(mauvais_mots) < 3:
            mauvais_mots.add(random.choice(["amour", "paix", "joie"]))

        question = verset_question["text"].replace(mot_a_retirer, "_____", 1)
        options = list(mauvais_mots) + [mot_correct]
        random.shuffle(options)

        ref = f"{verset_question.get('book_name')} {verset_question.get('chapter')}:{verset_question.get('verse')}"
        return {"question": question, "options": options, "reponse_correcte": mot_correct, "reference": ref}

    except Exception as e:
        return {"error": f"Erreur interne: {e}"}

# --- Routes ---
@router.post("/qcm/batch")
def generer_qcm_batch(data: BatchQcmRequest):
    questions, mots_deja = [], set(data.mots_deja_utilises or [])
    for _ in range(data.nombre):
        q = jeu_qcm_single(ReferenceRequest(
            reference=data.reference, niveau=data.niveau, mots_deja_utilises=list(mots_deja)
        ))
        if "error" in q:
            continue
        mots_deja.add(q["reponse_correcte"].lower())
        questions.append({
            "question": q["question"], "options": q["options"],
            "answer": q["reponse_correcte"], "reference": q["reference"]
        })

    if not questions:
        raise HTTPException(500, "Impossible de générer les questions.")
    return {"questions": questions}

@router.post("/duel/texte-a-trous/batch")
def generer_texte_trous_batch(data: BatchQcmRequest):
    jeux = []
    livre, chapitre, numeros = parse_reference(data.reference)
    versets_selectionnes = get_versets(livre, chapitre, numeros)

    for _ in range(data.nombre):
        if not versets_selectionnes:
            continue
        v = random.choice(versets_selectionnes)
        mots = v["text"].split()
        difficulte = {"facile": 2, "moyen": 4, "difficile": 6}
        nb_cacher = min(difficulte.get(data.niveau.lower(), 2), len(mots)//2)

        indices = [i for i, mot in enumerate(mots) if len(mot) > 3]
        if not indices:
            continue
        random.shuffle(indices)
        choisis = sorted(indices[:nb_cacher])

        reponses = [re.sub(r'[^\w\s-]', '', mots[i]) for i in choisis]
        for i in choisis:
            mots[i] = "_____"

        ref = f"{v.get('book_name')} {v.get('chapter')}:{v.get('verse')}"
        jeux.append({
            "verset_modifie": " ".join(mots),
            "reponses": reponses,
            "indices": choisis,
            "reference": ref,
            "texte_original": v["text"]
        })

    if not jeux:
        raise HTTPException(500, "Impossible de générer les jeux de texte à trous.")
    return {"jeux": jeux}

@router.post("/duel/ordre/batch")
def generer_ordre_batch(data: BatchQcmRequest):
    jeux = []
    livre, chapitre, numeros = parse_reference(data.reference)
    versets_selectionnes = get_versets(livre, chapitre, numeros)

    for _ in range(data.nombre):
        if not versets_selectionnes:
            continue
        v = random.choice(versets_selectionnes)
        mots = v["text"].split()
        if len(mots) < 5:
            continue
        melanges = mots.copy()
        random.shuffle(melanges)

        ref = f"{v.get('book_name')} {v.get('chapter')}:{v.get('verse')}"
        jeux.append({
            "mots_melanges": melanges,
            "ordre_correct": mots,
            "texte_original": v["text"],
            "reference": ref
        })

    if not jeux:
        raise HTTPException(500, "Impossible de générer les jeux de remise en ordre.")
    return {"jeux": jeux}
