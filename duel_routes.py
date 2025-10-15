from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import json
import random
import re
from typing import List, Optional
from bible_loader import bible_loader

router = APIRouter()

# --- Fonction helper ---
def parse_and_fetch_verses(reference: str, request: Request) -> List[dict]:
    """Parse une référence et récupère les versets (API ou JSON local)."""
    language = getattr(request.state, "language", "fr")
    
    if language == "en" and bible_loader.is_api_mode("en"):
        verses = bible_loader.get_verses_for_reference(reference, "en")
        if not verses:
            raise HTTPException(404, "Verses not found via API")
        return verses
    
    verses = bible_loader.get_verses("fr")
    
    try:
        match_plage = re.match(r"^(.*\D)\s*(\d+):(\d+)-(\d+)$", reference.strip())
        if match_plage:
            book, chapter, start_v, end_v = match_plage.groups()
            book = book.strip()
            chapter = int(chapter)
            verse_nums = list(range(int(start_v), int(end_v) + 1))
            
            return [
                v for v in verses
                if v.get("book_name", "").strip().lower() == book.lower()
                and int(v.get("chapter")) == chapter
                and int(v.get("verse")) in verse_nums
            ]
        
        match_unique = re.match(r"^(.*\D)\s*(\d+):(\d+)$", reference.strip())
        if match_unique:
            book, chapter, verse = match_unique.groups()
            return [
                v for v in verses
                if v.get("book_name", "").strip().lower() == book.strip().lower()
                and int(v.get("chapter")) == int(chapter)
                and int(v.get("verse")) == int(verse)
            ]
        
        match_chapitre = re.match(r"^(.*\D)\s*(\d+)$", reference.strip())
        if match_chapitre:
            book, chapter = match_chapitre.groups()
            return [
                v for v in verses
                if v.get("book_name", "").strip().lower() == book.strip().lower()
                and int(v.get("chapter")) == int(chapter)
            ]
    except Exception as e:
        print(f"Erreur parsing: {e}")
        raise HTTPException(400, f"Invalid reference: {reference}")
    
    return []

def normalize_text(s: str) -> str:
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

# --- Modèles ---
class BatchQcmRequest(BaseModel):
    reference: str
    niveau: str
    nombre: int
    mots_deja_utilises: Optional[List[str]] = None

class ReferenceRequest(BaseModel):
    reference: str
    niveau: str
    mots_deja_utilises: Optional[List[str]] = None

# --- Génération QCM ---
def jeu_qcm_single(data: ReferenceRequest, request: Request):
    try:
        versets_selectionnes = parse_and_fetch_verses(data.reference, request)
        
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
        
        # Pour les distracteurs avec l'API, on doit être plus créatifs
        mauvais_mots = set()
        language = getattr(request.state, "language", "fr")
        
        if language == "en" and bible_loader.is_api_mode("en"):
            # Mode API : utiliser des mots du même verset ou des mots bibliques communs
            mots_disponibles = {normalize_text(m) for m in mots if len(m) > 3}
            mots_disponibles.discard(mot_correct.lower())
            
            if len(mots_disponibles) >= 3:
                mauvais_mots = set(random.sample(list(mots_disponibles), 3))
            else:
                # Fallback avec des mots bibliques anglais courants
                fallback_words = ["love", "faith", "hope", "grace", "peace", "truth", "light", "life", "lord", "god"]
                mauvais_mots = set(random.sample(fallback_words, min(3, len(fallback_words))))
        else:
            # Mode JSON local (français) - logique existante
            pool_autres = bible_loader.get_verses("fr")
            
            if data.niveau.lower() == "facile":
                pool = [v for v in pool_autres if v.get("book_name") != verset_question.get("book_name")]
            elif data.niveau.lower() == "difficile":
                pool = [v for v in pool_autres if v.get("book_name") == verset_question.get("book_name") 
                                             and v.get("chapter") == verset_question.get("chapter")]
            else:
                pool = [v for v in pool_autres if v.get("book_name") == verset_question.get("book_name")]
            
            random.shuffle(pool)
            while len(mauvais_mots) < 3 and pool:
                mots_option = pool.pop()['text'].split()
                mots_propres = {normalize_text(m) for m in mots_option if len(m) > 3}
                mots_propres.discard(mot_correct.lower())
                if mots_propres:
                    mauvais_mots.add(random.choice(list(mots_propres)))
        
        while len(mauvais_mots) < 3:
            mauvais_mots.add(random.choice(["love", "peace", "faith"] if language == "en" else ["amour", "paix", "joie"]))
        
        question = verset_question["text"].replace(mot_a_retirer, "_____", 1)
        options = list(mauvais_mots) + [mot_correct]
        random.shuffle(options)
        
        ref = f"{verset_question['book_name']} {verset_question['chapter']}:{verset_question['verse']}"
        return {
            "question": question,
            "options": options,
            "reponse_correcte": mot_correct,
            "reference": ref
        }
    except Exception as e:
        return {"error": f"Erreur: {e}"}

# --- Routes ---
@router.post("/qcm/batch")
def generer_qcm_batch(data: BatchQcmRequest, request: Request):
    """Génère un batch de QCM avec support multilingue."""
    questions, mots_deja = [], set(data.mots_deja_utilises or [])
    
    for _ in range(data.nombre):
        q = jeu_qcm_single(
            ReferenceRequest(
                reference=data.reference,
                niveau=data.niveau,
                mots_deja_utilises=list(mots_deja)
            ),
            request
        )
        
        if "error" in q:
            continue
        
        mots_deja.add(q["reponse_correcte"].lower())
        questions.append({
            "question": q["question"],
            "options": q["options"],
            "answer": q["reponse_correcte"],
            "reference": q["reference"]
        })
    
    if not questions:
        raise HTTPException(500, "Impossible de générer les questions.")
    
    return {"questions": questions}

@router.post("/duel/texte-a-trous/batch")
def generer_texte_trous_batch(data: BatchQcmRequest, request: Request):
    """Génère un batch de jeux texte à trous avec support multilingue."""
    jeux = []
    versets_selectionnes = parse_and_fetch_verses(data.reference, request)
    
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
        
        ref = f"{v['book_name']} {v['chapter']}:{v['verse']}"
        jeux.append({
            "verset_modifie": " ".join(mots),
            "reponses": reponses,
            "indices": choisis,
            "reference": ref,
            "texte_original": v["text"]
        })
    
    if not jeux:
        raise HTTPException(500, "Impossible de générer les jeux.")
    
    return {"jeux": jeux}

@router.post("/duel/ordre/batch")
def generer_ordre_batch(data: BatchQcmRequest, request: Request):
    """Génère un batch de jeux de remise en ordre avec support multilingue."""
    jeux = []
    versets_selectionnes = parse_and_fetch_verses(data.reference, request)
    
    for _ in range(data.nombre):
        if not versets_selectionnes:
            continue
        
        v = random.choice(versets_selectionnes)
        mots = v["text"].split()
        
        if len(mots) < 5:
            continue
        
        melanges = mots.copy()
        random.shuffle(melanges)
        
        ref = f"{v['book_name']} {v['chapter']}:{v['verse']}"
        jeux.append({
            "mots_melanges": melanges,
            "ordre_correct": mots,
            "texte_original": v["text"],
            "reference": ref
        })
    
    if not jeux:
        raise HTTPException(500, "Impossible de générer les jeux de remise en ordre.")
    
    return {"jeux": jeux}