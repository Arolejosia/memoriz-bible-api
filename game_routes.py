from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
import json
import random
import string
from typing import List, Optional
import os
import requests
import re
from dotenv import load_dotenv
from bible_loader import bible_loader

load_dotenv()

# --- Configuration de l'IA ---
TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
API_URL = "https://api.together.xyz/v1/chat/completions"

router = APIRouter()

# ============================================
# 🆕 FONCTION HELPER POUR RÉCUPÉRER LES VERSETS
# ============================================
def parse_and_fetch_verses(reference: str, request: Request) -> list:
    """Parse une référence et récupère les versets (API ou JSON local)."""
    language = getattr(request.state, "language", "fr")
    
    # Si anglais (mode API)
    if language == "en" and bible_loader.is_api_mode("en"):
        verses = bible_loader.get_verses_for_reference(reference, "en")
        if not verses:
            raise HTTPException(404, "Verses not found via API")
        return verses
    
    # Si français (JSON local)
    verses = bible_loader.get_verses("fr")
    
    # Parser la référence
    try:
        # Plage de versets (ex: Jean 3:16-18)
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
        
        # Verset unique (ex: Jean 3:16)
        match_unique = re.match(r"^(.*\D)\s*(\d+):(\d+)$", reference.strip())
        if match_unique:
            book, chapter, verse = match_unique.groups()
            book = book.strip()
            
            return [
                v for v in verses
                if v.get("book_name", "").strip().lower() == book.lower()
                and int(v.get("chapter")) == int(chapter)
                and int(v.get("verse")) == int(verse)
            ]
        
        # Chapitre complet (ex: Jean 3)
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

# --- Modèles de données ---
class ReferenceRequest(BaseModel):
    reference: str
    niveau: str
    mots_deja_utilises: Optional[List[str]] = None

class RandomQcmRequest(BaseModel):
    mots_deja_utilises: Optional[List[str]] = None
    livre: Optional[str] = None
    chapitre: Optional[int] = None

class VerificationRequest(BaseModel):
    reponses_utilisateur: List[str]
    reponses_correctes: List[str]

class RandomJeuRequest(BaseModel):
    niveau: str
    longueur: str
    livre: Optional[str] = None
    chapitre: Optional[int] = None

class ReferenceQuestionRequest(BaseModel):
    difficulty: str
    source_group: Optional[str] = None
    source_refs: Optional[List[str]] = None
    source_book: Optional[str] = None

class RemettreEnOrdreRequest(BaseModel):
    reference: str

# Dictionnaire des catégories de livres
BOOK_GROUPS = {
    "ancien_testament": [
        "Genèse", "Exode", "Lévitique", "Nombres", "Deutéronome", "Josué", "Juges", "Ruth", "1 Samuel", "2 Samuel", "1 Rois", "2 Rois",
        "1 Chroniques", "2 Chroniques", "Esdras", "Néhémie", "Esther", "Job", "Psaumes", "Proverbes", "Ecclésiaste", "Cantique des Cantiques", "Ésaïe",
        "Jérémie", "Lamentations", "Ézéchiel", "Daniel", "Osée", "Joël", "Amos", "Abdias", "Jonas", "Michée", "Nahum", "Habacuc", "Sophonie", "Aggée",
        "Zacharie", "Malachie"
    ],
    "nouveau_testament": [
        "Matthieu", "Marc", "Luc", "Jean", "Actes", "Romains", "1 Corinthiens", "2 Corinthiens", "Galates", "Éphésiens", "Philippiens", "Colossiens",
        "1 Thessaloniciens", "2 Thessaloniciens", "1 Timothée", "2 Timothée", "Tite", "Philémon", "Hébreux", "Jacques", "1 Pierre", "2 Pierre",
        "1 Jean", "2 Jean", "3 Jean", "Jude", "Apocalypse"
    ],
    "pentateuque": ["Genèse", "Exode", "Lévitique", "Nombres", "Deutéronome"],
    "historiques": ["Josué", "Juges", "Ruth", "1 Samuel", "2 Samuel", "1 Rois", "2 Rois", "1 Chroniques", "2 Chroniques", "Esdras", "Néhémie", "Esther"],
    "poetiques": ["Job", "Psaumes", "Proverbes", "Ecclésiaste", "Cantique des Cantiques"],
    "prophetes_majeurs": ["Ésaïe", "Jérémie", "Lamentations", "Ézéchiel", "Daniel"],
    "prophetes_mineurs": ["Osée", "Joël", "Amos", "Abdias", "Jonas", "Michée", "Nahum", "Habacuc", "Sophonie", "Aggée", "Zacharie", "Malachie"],
    "evangiles": ["Matthieu", "Marc", "Luc", "Jean"],
    "histoire_nt": ["Actes"],
    "epitres_paul": ["Romains", "1 Corinthiens", "2 Corinthiens", "Galates", "Éphésiens", "Philippiens", "Colossiens", "1 Thessaloniciens", "2 Thessaloniciens", "1 Timothée", "2 Timothée", "Tite", "Philémon"],
    "epitres_generales": ["Hébreux", "Jacques", "1 Pierre", "2 Pierre", "1 Jean", "2 Jean", "3 Jean", "Jude"],
    "apocalypse": ["Apocalypse"],
}

def find_book_category(book_name: str) -> Optional[str]:
    for category, books in BOOK_GROUPS.items():
        if book_name in books:
            return category.replace("_", " ").capitalize()
    return None

def normalize_text(s: str) -> str:
    """Met en minuscule, retire les accents et la ponctuation."""
    s = s.lower().strip()
    replacements = (
        ("á", "a"), ("à", "a"), ("â", "a"), ("ä", "a"),
        ("é", "e"), ("è", "e"), ("ê", "e"), ("ë", "e"),
        ("í", "i"), ("î", "i"), ("ï", "i"),
        ("ó", "o"), ("ô", "o"), ("ö", "o"),
        ("ú", "u"), ("ù", "u"), ("û", "u"), ("ü", "u"),
        ("ç", "c"),
    )
    for a, b in replacements:
        s = s.replace(a, b)
    return s.translate(str.maketrans('', '', string.punctuation))

def levenshtein_distance(s1: str, s2: str) -> int:
    """Calcule la distance de Levenshtein entre deux chaînes."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def are_strings_similar(s1: str, s2: str, tolerance: float = 0.85) -> bool:
    """Vérifie si deux chaînes sont similaires au-delà d'un seuil de tolérance."""
    norm_s1 = normalize_text(s1)
    norm_s2 = normalize_text(s2)
    
    if not norm_s1 or not norm_s2:
        return norm_s1 == norm_s2

    distance = levenshtein_distance(norm_s1, norm_s2)
    max_len = max(len(norm_s1), len(norm_s2))
    similarity = 1 - (distance / max_len)
    
    return similarity >= tolerance

def generer_mots_ia(contexte_pour_ia, mot_correct, livre):
    """Génère des mots distracteurs avec l'IA ou utilise un fallback."""
    try:
        if not TOGETHER_API_KEY:
            raise Exception("Clé API manquante")
            
        headers = {"Authorization": f"Bearer {TOGETHER_API_KEY}"}
        
        prompt = f"""
        Contexte biblique : "{contexte_pour_ia}" (du livre {livre})
        
        Le mot manquant est "{mot_correct}".
        
        Génère exactement 3 mots distracteurs bibliques qui :
        1. Sont plausibles dans ce contexte
        2. Sont différents de "{mot_correct}"
        3. Sont des mots français courants dans la Bible
        
        Réponds uniquement avec les 3 mots, séparés par des virgules.
        """
        
        data = {
            "model": "meta-llama/Llama-2-7b-chat-hf",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 50,
            "temperature": 0.7
        }
        
        response = requests.post(API_URL, json=data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            mots = [mot.strip() for mot in content.split(",")]
            if len(mots) >= 3:
                return mots[:3]
        
        raise Exception("Réponse IA invalide")
        
    except Exception as e:
        print(f"Erreur IA: {e}")
        return ["amour", "paix", "joie"]

# ============================================
# ROUTES DE L'API
# ============================================

@router.post("/jeu")
def jeu_texte_a_trous(data: ReferenceRequest, request: Request):
    """Jeu de texte à trous avec support multilingue."""
    try:
        versets_selectionnes = parse_and_fetch_verses(data.reference, request)
        
        if not versets_selectionnes:
            return {"error": "Aucun verset trouvé pour cette référence."}
        
        nombre_de_versets = len(versets_selectionnes)
        passage_pour_jeu = []
        
        if nombre_de_versets > 3:
            passage_pour_jeu = [random.choice(versets_selectionnes)]
        else:
            passage_pour_jeu = versets_selectionnes
        
        if not passage_pour_jeu:
            return {"error": "Impossible de générer un passage."}
        
        texte_complet = " ".join([v["text"] for v in passage_pour_jeu])
        
        premier = passage_pour_jeu[0]
        dernier = passage_pour_jeu[-1]
        
        if premier.get('verse') == dernier.get('verse'):
            reference_exacte = f"{premier['book_name']} {premier['chapter']}:{premier['verse']}"
        else:
            reference_exacte = f"{premier['book_name']} {premier['chapter']}:{premier['verse']}-{dernier['verse']}"
        
        mots = texte_complet.split()
        nb_mots = {"débutant": 2, "intermédiaire": 4, "expert": 6}.get(data.niveau.lower(), 2)
        nb_mots = min(nb_mots, len(mots) // 2)
        
        indices_disponibles = [i for i, mot in enumerate(mots) if len(mot) > 3]
        if not indices_disponibles:
            return {"error": "Le passage est trop court."}
        
        random.shuffle(indices_disponibles)
        indices_choisis = sorted(indices_disponibles[:nb_mots])
        
        reponses = [re.sub(r'[^\w\s-]', '', mots[i]) for i in indices_choisis]
        for i in indices_choisis:
            mots[i] = "_____"
        
        return {
            "verset_modifie": " ".join(mots),
            "reponses": reponses,
            "indices": indices_choisis,
            "reference": reference_exacte
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {"error": f"Erreur interne: {e}"}

@router.post("/verifier")
def verifier_reponses(data: VerificationRequest):
    """Vérifie les réponses de l'utilisateur."""
    resultats = []
    for i, reponse_user in enumerate(data.reponses_utilisateur):
        reponse_correcte = data.reponses_correctes[i]
        est_correct = are_strings_similar(reponse_user, reponse_correcte)
        resultats.append(est_correct)
    
    return {"resultats": resultats}

@router.get("/passage")
def get_passage(ref: str = Query(...), request: Request = None):
    """Récupère un passage avec support multilingue."""
    try:
        versets = parse_and_fetch_verses(ref, request)
        
        if not versets:
            return []
        
        versets.sort(key=lambda v: int(v.get('verse', 0)))
        
        return [
            {
                "reference": f"{v['book_name']} {v['chapter']}:{v['verse']}",
                "text": v['text']
            }
            for v in versets
        ]
        
    except Exception as e:
        print(f"Error in /passage: {e}")
        return []

@router.post("/qcm")
def jeu_qcm(data: ReferenceRequest, request: Request):
    """Génère une question QCM avec support multilingue."""
    try:
        versets_selectionnes = parse_and_fetch_verses(data.reference, request)
        
        if not versets_selectionnes:
            return {"error": "Aucun verset trouvé pour cette référence."}
        
        verset_question = random.choice(versets_selectionnes)
        
        mots_utilises = {normalize_text(mot) for mot in (data.mots_deja_utilises or [])}
        
        mots = verset_question["text"].split()
        
        mots_eligibles = {normalize_text(mot) for mot in mots if len(mot) > 3}
        mots_non_utilises = list(mots_eligibles - mots_utilises)
        
        if not mots_non_utilises and mots_eligibles:
            mots_non_utilises = list(mots_eligibles)
        
        if not mots_non_utilises:
            return {"error": "Félicitations ! Vous avez mémorisé tous les mots de ce passage."}

        mot_correct = random.choice(mots_non_utilises)
        mot_a_retirer = next((mot for mot in mots if normalize_text(mot) == mot_correct), mot_correct)

        # Générer distracteurs
        mauvais_mots = set()
        language = getattr(request.state, "language", "fr")
        
        if language == "en" and bible_loader.is_api_mode("en"):
            # Mode API : utiliser mots du même verset ou fallback
            mots_disponibles = {normalize_text(m) for m in mots if len(m) > 3}
            mots_disponibles.discard(mot_correct.lower())
            
            if len(mots_disponibles) >= 3:
                mauvais_mots = set(random.sample(list(mots_disponibles), 3))
            else:
                fallback = ["love", "faith", "hope", "grace", "peace", "truth", "light", "life"]
                mauvais_mots = set(random.sample(fallback, min(3, len(fallback))))
        else:
            # Mode JSON local
            versets_all = bible_loader.get_verses("fr")
            
            if data.niveau == "facile":
                pool = [v for v in versets_all if v.get("book_name") != verset_question.get("book_name")]
            elif data.niveau == "difficile":
                pool = [v for v in versets_all if v.get("book_name") == verset_question.get("book_name") 
                                                 and v.get("chapter") == verset_question.get("chapter")]
            else:
                pool = [v for v in versets_all if v.get("book_name") == verset_question.get("book_name")]

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
        
        verset_ref = f"{verset_question.get('book_name')} {verset_question.get('chapter')}:{verset_question.get('verse')}"

        return {
            "question": question,
            "options": options,
            "reponse_correcte": mot_correct,
            "reference": verset_ref
        }

    except Exception as e:
        return {"error": f"Une erreur interne est survenue: {e}"}

@router.get("/verser")
def get_single_verse(ref: str = Query(...), request: Request = None):
    """Récupère un seul verset avec support multilingue."""
    try:
        versets = parse_and_fetch_verses(ref, request)
        
        if versets:
            return {"text": versets[0].get("text", "Texte non trouvé.")}
        
        raise HTTPException(status_code=404, detail=f"Verset '{ref}' non trouvé.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generer-question-reference")
def generate_reference_question(request_data: ReferenceQuestionRequest, request: Request):
    """Génère une question de référence avec support multilingue."""
    language = getattr(request.state, "language", "fr")
    
    # Pour l'instant, cette route fonctionne uniquement en français
    if language == "en":
        return {"error": "Cette fonctionnalité n'est disponible qu'en français pour le moment."}
    
    versets = bible_loader.get_verses("fr")
    pool_source = versets
    is_specific_book = request_data.source_book is not None
    source_book_names = set()

    if is_specific_book:
        pool_source = [v for v in versets if v.get("book_name", "").lower() == request_data.source_book.lower()]
    elif request_data.source_group:
        source_book_names = {book.lower() for book in BOOK_GROUPS.get(request_data.source_group, [])}
        pool_source = [v for v in versets if v.get("book_name", "").lower() in source_book_names]

    if not pool_source:
        raise HTTPException(status_code=400, detail="La source choisie est vide.")

    verset_correct = random.choice(pool_source)
    texte_de_la_question = verset_correct.get("text", "")
    
    options = set()
    reponse_correcte = ""

    if is_specific_book:
        if request_data.difficulty == "facile":
            reponse_correcte = f"{verset_correct.get('book_name')} {verset_correct.get('chapter')}"
            options.add(reponse_correcte)
            pool_pertinent = {f"{v.get('book_name')} {v.get('chapter')}" for v in pool_source if f"{v.get('book_name')} {v.get('chapter')}" != reponse_correcte}
            pool_general = {f"{v.get('book_name')} {v.get('chapter')}" for v in versets if v.get("book_name") != request_data.source_book}
            if len(pool_pertinent) >= 2: options.update(random.sample(list(pool_pertinent), 2))
            if len(options) < 4 and pool_general: options.add(random.choice(list(pool_general)))
        else:
            reponse_correcte = f"{verset_correct.get('book_name')} {verset_correct.get('chapter')}:{verset_correct.get('verse')}"
            options.add(reponse_correcte)
            pool_distracteurs = [v for v in pool_source if v != verset_correct]
            if len(pool_distracteurs) >= 3:
                for d in random.sample(pool_distracteurs, 3):
                    options.add(f"{d.get('book_name')} {d.get('chapter')}:{d.get('verse')}")
    else:
        if request_data.difficulty == "facile":
            reponse_correcte = verset_correct.get("book_name")
            options.add(reponse_correcte)
            pool_pertinent = {v.get("book_name") for v in pool_source if v.get("book_name") != reponse_correcte}
            pool_general = {v.get("book_name") for v in versets if v.get("book_name", "").lower() not in source_book_names}
            if len(pool_pertinent) >= 2: options.update(random.sample(list(pool_pertinent), 2))
            if len(options) < 4 and pool_general: options.add(random.choice(list(pool_general)))
        elif request_data.difficulty == "moyen":
            reponse_correcte = f"{verset_correct.get('book_name')} {verset_correct.get('chapter')}"
            options.add(reponse_correcte)
            pool_distracteurs = [v for v in pool_source if f"{v.get('book_name')} {v.get('chapter')}" != reponse_correcte]
            while len(options) < 4 and pool_distracteurs:
                d = random.choice(pool_distracteurs)
                options.add(f"{d.get('book_name')} {d.get('chapter')}")
                pool_distracteurs.remove(d)
        else:
            reponse_correcte = f"{verset_correct.get('book_name')} {verset_correct.get('chapter')}:{verset_correct.get('verse')}"
            options.add(reponse_correcte)
            distracteurs_pool = [v for v in pool_source if v != verset_correct]
            if len(distracteurs_pool) >= 3:
                for d in random.sample(distracteurs_pool, 3):
                    options.add(f"{d.get('book_name')} {d.get('chapter')}:{d.get('verse')}")

    options_list = list(options)
    while len(options_list) < 4:
        d = random.choice(versets)
        options_list.append(f"{d.get('book_name')} {d.get('chapter')}:{d.get('verse')}")
    random.shuffle(options_list)

    return {
        "question_text": texte_de_la_question,
        "options": options_list,
        "reponse_correcte": reponse_correcte
    }

@router.post("/qcm/random")
def jeu_qcm_aleatoire(data: ReferenceRequest, request: Request):
    """Génère une question QCM aléatoire."""
    language = getattr(request.state, "language", "fr")
    
    # Cette route fonctionne uniquement en français pour l'instant
    if language == "en":
        return {"error": "Cette fonctionnalité n'est disponible qu'en français pour le moment."}
    
    try:
        versets = bible_loader.get_verses("fr")
        mots_utilises = set(data.mots_deja_utilises or [])
        
        verset_question = None
        indices_disponibles = []
        
        tentatives = 0
        while not indices_disponibles and tentatives < 50:
            verset_question = random.choice(versets)
            if len(verset_question["text"].split()) >= 5:
                mots = verset_question["text"].split()
                mots_longs_indices = [i for i, mot in enumerate(mots) if len(mot) > 3]
                indices_disponibles = [i for i in mots_longs_indices if re.sub(r'[^\w\s-]', '', mots[i]).lower() not in mots_utilises]
            tentatives += 1

        if not indices_disponibles:
            return {"error": "Impossible de trouver un nouveau mot à mémoriser."}

        livre = verset_question.get("book_name", "Inconnu")
        mots = verset_question["text"].split()
        
        index_mot_a_retirer = random.choice(indices_disponibles)
        mot_a_retirer = mots[index_mot_a_retirer]
        mot_correct = re.sub(r'[^\w\s-]', '', mot_a_retirer)

        debut_contexte = max(0, index_mot_a_retirer - 3)
        partie_contexte = mots[debut_contexte:index_mot_a_retirer]
        contexte_pour_ia = " ".join(partie_contexte) + " _____"

        mauvais_mots = generer_mots_ia(contexte_pour_ia, mot_correct, livre)

        question = verset_question["text"].replace(mot_a_retirer, "_____", 1)

        options = mauvais_mots + [mot_correct]
        random.shuffle(options)

        return {
            "question": question,
            "options": options,
            "reponse_correcte": mot_correct
        }

    except Exception as e:
        return {"error": f"Une erreur interne est survenue: {e}"}

@router.post("/remettre-en-ordre")
def get_unscrambled_verse_game(data: RemettreEnOrdreRequest, request: Request):
    """Jeu de remise en ordre des mots avec support multilingue."""
    try:
        versets_selectionnes = parse_and_fetch_verses(data.reference, request)

        if not versets_selectionnes:
            return {"error": "Aucun verset trouvé pour cette référence."}

        verset_choisi = random.choice(versets_selectionnes)
        texte_original = verset_choisi["text"]
        
        mots = texte_original.split()
        mots_melanges = mots.copy()
        random.shuffle(mots_melanges)
        
        ref_exacte = f"{verset_choisi.get('book_name')} {verset_choisi.get('chapter')}:{verset_choisi.get('verse')}"

        jeu_data = {
            "mots_melanges": mots_melanges,
            "ordre_correct": mots,
            "texte_original": texte_original,
            "reference": ref_exacte
        }
        return {"versets": [jeu_data]}
    except Exception as e:
        return {"error": f"Une erreur interne est survenue: {e}"}