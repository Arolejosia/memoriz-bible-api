from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import json
import random
import string
from typing import List, Optional
import os
import requests
import re
from dotenv import load_dotenv

load_dotenv()

# --- Configuration de l'IA ---
TOGETHER_API_KEY = os.environ.get("TOGETHER_API_KEY")
API_URL = "https://api.together.xyz/v1/chat/completions"

router = APIRouter()

# --- Chargement des données ---
try:
    with open("segond_1910.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        if "verses" in raw_data:
            versets = raw_data["verses"]
        else:
            print("Erreur: La clé 'verses' est introuvable dans le fichier JSON.")
            versets = []
except FileNotFoundError:
    print("Erreur: Le fichier 'segond_1910.json' est introuvable.")
    versets = []
except json.JSONDecodeError:
    print("Erreur: Le fichier JSON est mal formaté.")
    versets = []

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
    longueur: str # 'court' ou 'long'
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

def get_bible_data():
    """
    Loads the bible data from the JSON file if it hasn't been loaded yet.
    """
    global versets
    if not versets:
        print("Loading bible data from JSON file for the first time...")
        try:
            with open("segond_1910.json", "r", encoding="utf-8") as f:
                versets = json.load(f).get("verses", [])
            print("Bible data loaded successfully.")
        except Exception as e:
            print(f"CRITICAL ERROR: Could not load bible data. {e}")
            versets = []
    return versets

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
    
    # Retire la ponctuation
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
    
    if not norm_s1 or not norm_s2: # Gère les chaînes vides
        return norm_s1 == norm_s2

    distance = levenshtein_distance(norm_s1, norm_s2)
    max_len = max(len(norm_s1), len(norm_s2))
    similarity = 1 - (distance / max_len)
    
    return similarity >= tolerance

def generer_jeu_depuis_texte(texte: str, niveau: str):
    mots = texte.split()
    mots_a_masquer = {"débutant": 2, "intermédiaire": 4, "expert": 6}.get(niveau.lower(), 2)
    mots_a_masquer = min(mots_a_masquer, len(mots))
    
    indices_disponibles = list(range(len(mots)))
    random.shuffle(indices_disponibles)
    indices_choisis = sorted(indices_disponibles[:mots_a_masquer])

    reponses = [mots[i] for i in indices_choisis]
    for i in indices_choisis:
        mots[i] = "_____"

    return " ".join(mots), reponses, indices_choisis

def find_verse_in_data(ref: str):
    try:
        match = re.match(r"^(.*\D)\s*(\d+):(\d+)$", ref.strip())
        if not match: return None
        
        book_name, chapter, verse_num = match.groups()
        book_name = book_name.strip()

        return next((
            v for v in versets
            if v.get("book_name", "").lower() == book_name.lower() and
               str(v.get("chapter")) == chapter and
               str(v.get("verse")) == verse_num
        ), None)
    except:
        return None

def generer_mots_ia(contexte_pour_ia, mot_correct, livre):
    """
    Génère des mots distracteurs avec l'IA ou utilise un fallback.
    """
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

# --- Routes de l'API ---
@router.post("/jeu")
def jeu_texte_a_trous(data: ReferenceRequest):
    versets = get_bible_data()
    """
    Gère les passages courts et longs pour le jeu de texte à trous.
    """
    try:
        # 1. Analyse de la référence
        reference = data.reference.strip()
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

        # 2. Sélection des versets
        if numeros_versets:
            versets_selectionnes = [v for v in versets if v.get("book_name", "").strip().lower() == livre.lower() and v.get("chapter") == chapitre and v.get("verse") in numeros_versets]
        else:
            versets_selectionnes = [v for v in versets if v.get("book_name", "").strip().lower() == livre.lower() and v.get("chapter") == chapitre]

        if not versets_selectionnes:
            return {"error": "Aucun verset trouvé pour cette référence."}

        # ✅ NOUVELLE LOGIQUE : Gestion des passages longs vs courts
        nombre_de_versets = len(versets_selectionnes)
        passage_pour_jeu = []

        if nombre_de_versets > 3:
            # Si le passage est long, on en choisit un seul verset au hasard
            passage_pour_jeu = [random.choice(versets_selectionnes)]
        else:
            # Si le passage est de 3 versets ou moins, on les prend tous
            passage_pour_jeu = versets_selectionnes

        if not passage_pour_jeu:
            return {"error": "Impossible de générer un passage à partir de cette référence."}

        # 3. Construction du jeu à partir du passage sélectionné
        texte_complet = " ".join([v["text"] for v in passage_pour_jeu])
        
        # 4. Création de la référence exacte pour l'affichage
        premier_verset = passage_pour_jeu[0]
        dernier_verset = passage_pour_jeu[-1]
        ref_livre = premier_verset.get('book_name')
        ref_chapitre = premier_verset.get('chapter')
        ref_verset_debut = premier_verset.get('verse')
        ref_verset_fin = dernier_verset.get('verse')

        if ref_verset_debut == ref_verset_fin:
            reference_exacte = f"{ref_livre} {ref_chapitre}:{ref_verset_debut}"
        else:
            reference_exacte = f"{ref_livre} {ref_chapitre}:{ref_verset_debut}-{ref_verset_fin}"

        # 5. Logique du texte à trous
        mots = texte_complet.split()
        nb_mots_a_cacher = {"débutant": 2, "intermédiaire": 4, "expert": 6}.get(data.niveau.lower(), 2)
        nb_mots_a_cacher = min(nb_mots_a_cacher, len(mots) // 2)

        indices_disponibles = [i for i, mot in enumerate(mots) if len(mot) > 3]
        if not indices_disponibles:
             return {"error": "Le passage est trop court pour créer un jeu."}
        
        random.shuffle(indices_disponibles)
        indices_choisis = sorted(indices_disponibles[:nb_mots_a_cacher])

        reponses = [re.sub(r'[^\w\s-]', '', mots[i]) for i in indices_choisis]
        for i in indices_choisis:
            mots[i] = "_____"
        
        texte_modifie = " ".join(mots)

        return {
            "verset_modifie": texte_modifie,
            "reponses": reponses,
            "indices": indices_choisis,
            "reference": reference_exacte
        }

    except Exception as e:
        return {"error": f"Une erreur interne est survenue: {e}"}

@router.post("/verifier")
def verifier_reponses(data: VerificationRequest):
    """
    Vérifie les réponses de l'utilisateur contre les bonnes réponses
    en utilisant la comparaison flexible.
    """
    resultats = []
    for i, reponse_user in enumerate(data.reponses_utilisateur):
        reponse_correcte = data.reponses_correctes[i]
        est_correct = are_strings_similar(reponse_user, reponse_correcte)
        resultats.append(est_correct)
    
    return {"resultats": resultats}

@router.get("/passage")
def get_passage(ref: str = Query(..., description="Reference like 'Jean 3:16' or 'Psaumes 23:1-4'")):
    try:
        # 1. Essayer d'abord une plage de versets (Jean 3:16-17)
        match_plage = re.match(r"^(.*\D)\s*(\d+):(\d+)-(\d+)$", ref.strip())
        
        if match_plage:
            book_name, chapter_str, start_verse_str, end_verse_str = match_plage.groups()
            book_name = book_name.strip()
            chapitre = int(chapter_str)
            numeros_versets = list(range(int(start_verse_str), int(end_verse_str) + 1))

            versets_selectionnes = [
                v for v in versets if
                v.get("book_name", "").strip().lower() == book_name.lower() and
                int(v.get("chapter")) == chapitre and
                int(v.get("verse")) in numeros_versets
            ]

            if not versets_selectionnes:
                return []  # ✅ Retourne liste vide si rien trouvé

            versets_selectionnes.sort(key=lambda v: int(v['verse']))
            
            return [
                {"reference": f"{v['book_name']} {v['chapter']}:{v['verse']}", "text": v['text']}
                for v in versets_selectionnes
            ]
        
        # 2. Sinon, essayer un verset unique (Jean 3:16)
        match_unique = re.match(r"^(.*\D)\s*(\d+):(\d+)$", ref.strip())
        
        if match_unique:
            book_name, chapter_str, verse_str = match_unique.groups()
            book_name = book_name.strip()
            chapitre = int(chapter_str)
            verse_num = int(verse_str)
            
            # ✅ Chercher le verset unique
            verset_trouve = next((
                v for v in versets if
                v.get("book_name", "").strip().lower() == book_name.lower() and
                int(v.get("chapter")) == chapitre and
                int(v.get("verse")) == verse_num
            ), None)
            
            if verset_trouve:
                return [{
                    "reference": f"{verset_trouve['book_name']} {verset_trouve['chapter']}:{verset_trouve['verse']}",
                    "text": verset_trouve.get("text", "Text not found.")
                }]
            else:
                return []  # ✅ Retourne liste vide si pas trouvé
        
        # 3. Si aucun format ne match
        return []  # ✅ Retourne liste vide au lieu d'une exception

    except Exception as e:
        print(f"Error in /passage: {e}")
        return []  # ✅ Retourne liste vide en cas d'erreur
    try:
        # Check for a passage first (e.g., "Book C:V-V")
        match = re.match(r"^(.*\D)\s*(\d+):(\d+)-(\d+)$", ref.strip())
        
        if match:
            book_name, chapter_str, start_verse_str, end_verse_str = match.groups()
            book_name = book_name.strip()
            chapitre = int(chapter_str)
            numeros_versets = list(range(int(start_verse_str), int(end_verse_str) + 1))

            # ✅ THE FIX: Convert 'chapter' and 'verse' from JSON to int before comparing
            versets_selectionnes = [
                v for v in versets if
                v.get("book_name", "").strip().lower() == book_name.lower() and
                int(v.get("chapter")) == chapitre and
                int(v.get("verse")) in numeros_versets
            ]

            if not versets_selectionnes:
                return []

            # Sort to ensure correct order
            versets_selectionnes.sort(key=lambda v: int(v['verse']))
            
            return [
                {"reference": f"{v['book_name']} {v['chapter']}:{v['verse']}", "text": v['text']}
                for v in versets_selectionnes
            ]

        else:
            # If it's not a passage, handle as a single verse
            single_verse = find_verse_in_data(ref)
            if single_verse:
                return [{
                    "reference": f"{single_verse['book_name']} {single_verse['chapter']}:{single_verse['verse']}",
                    "text": single_verse.get("text", "Text not found.")
                }]
            else:
                 raise HTTPException(status_code=404, detail="Reference not found.")

    except Exception as e:
        print(f"Error in /passage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/qcm")
def jeu_qcm(data: ReferenceRequest):
    """
    Génère une question QCM à partir d'un verset choisi au hasard
    dans la sélection de l'utilisateur (courte ou longue).
    """
    try:
        reference = data.reference.strip()
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

        if numeros_versets:
            versets_selectionnes = [v for v in versets if v.get("book_name", "").strip().lower() == livre.lower() and v.get("chapter") == chapitre and v.get("verse") in numeros_versets]
        else:
            versets_selectionnes = [v for v in versets if v.get("book_name", "").strip().lower() == livre.lower() and v.get("chapter") == chapitre]

        if not versets_selectionnes:
            return {"error": "Aucun verset trouvé pour cette référence."}

        # ✅ LOGIQUE CLÉ : On choisit toujours un seul verset au hasard dans la sélection de l'utilisateur.
        verset_question = random.choice(versets_selectionnes)
        
        mots_utilises = {normalize_text(mot) for mot in (data.mots_deja_utilises or [])}
        
        mots = verset_question["text"].split()
        
        mots_eligibles = { normalize_text(mot) for mot in mots if len(mot) > 3 }
        mots_non_utilises = list(mots_eligibles - mots_utilises)
        
        cycle_recommence = False
        if not mots_non_utilises and mots_eligibles:
            mots_non_utilises = list(mots_eligibles)
            cycle_recommence = True
        
        if not mots_non_utilises:
            return {"error": "Félicitations ! Vous avez mémorisé tous les mots de ce passage."}

        mot_correct = random.choice(mots_non_utilises)
        mot_a_retirer = next((mot for mot in mots if normalize_text(mot) == mot_correct), mot_correct)

        mauvais_mots = set()
        
        if data.niveau == "facile":
            # Facile : On choisit des mots dans d'autres livres
            pool_autres_versets = [v for v in versets if v.get("book_name") != verset_question.get("book_name")]
        elif data.niveau == "difficile":
            # Difficile : On choisit des mots dans le même chapitre
            pool_autres_versets = [v for v in versets if v.get("book_name") == verset_question.get("book_name") and v.get("chapter") == verset_question.get("chapter")]
        else: # Moyen (par défaut)
            # Moyen : On choisit des mots dans le même livre (votre logique existante)
            pool_autres_versets = [v for v in versets if v.get("book_name") == verset_question.get("book_name")]

        # La logique pour peupler mauvais_mots à partir du pool reste la même
        random.shuffle(pool_autres_versets)
        while len(mauvais_mots) < 3 and pool_autres_versets:
            mots_option = pool_autres_versets.pop()['text'].split()
            mots_option_propres = {normalize_text(m) for m in mots_option if len(m) > 3}
            mots_option_propres.discard(mot_correct.lower())
            if mots_option_propres:
                mauvais_mots.add(random.choice(list(mots_option_propres)))

        # Fallback si on n'a toujours pas assez de mots
        while len(mauvais_mots) < 3:
            mauvais_mots.add(random.choice(["amour", "paix", "joie"]))
            
        # --- FIN DE LA NOUVELLE LOGIQUE ---

        question_pour_flutter = verset_question["text"].replace(mot_a_retirer, "_____", 1)
        options = list(mauvais_mots) + [mot_correct]
        random.shuffle(options)
        
        verset_ref = f"{verset_question.get('book_name')} {verset_question.get('chapter')}:{verset_question.get('verse')}"

        return {
            "question": question_pour_flutter,
            "options": options,
            "reponse_correcte": mot_correct,
            "reference": verset_ref
        }

    except Exception as e:
        return {"error": f"Une erreur interne est survenue: {e}"}

@router.get("/verser")
def get_single_verse(ref: str = Query(..., description="La référence biblique, ex: Jean 3:16")):
    """
    Récupère le texte d'un seul verset basé sur sa référence.
    C'est la route utilisée par la page Bibliothèque de Flutter.
    """
    try:
        parts = ref.rsplit(' ', 1)
        book_name = parts[0].strip()
        chapter_verse = parts[1].split(':')
        chapter = chapter_verse[0].strip()
        verse_num = chapter_verse[1].strip()
    except IndexError:
        raise HTTPException(status_code=400, detail="Format de référence invalide. Attendu : 'Livre Chapitre:Verset'")

    for verse_obj in versets:
        if (verse_obj.get("book_name", "").strip().lower() == book_name.lower() and
            str(verse_obj.get("chapter")) == chapter and
            str(verse_obj.get("verse")) == verse_num):
            
            return {"text": verse_obj.get("text", "Texte non trouvé.")}

    raise HTTPException(status_code=404, detail=f"Verset '{ref}' non trouvé.")

@router.post("/generer-question-reference")
def generate_reference_question(request: ReferenceQuestionRequest):
    # --- 1. Déterminer le pool de versets source ---
    pool_source = versets
    is_specific_book = request.source_book is not None
    source_book_names = set()

    if is_specific_book:
        pool_source = [v for v in versets if v.get("book_name", "").lower() == request.source_book.lower()]
    elif request.source_group:
        source_book_names = {book.lower() for book in BOOK_GROUPS.get(request.source_group, [])}
        pool_source = [v for v in versets if v.get("book_name", "").lower() in source_book_names]

    if not pool_source:
        raise HTTPException(status_code=400, detail="La source choisie est vide.")

    verset_correct = random.choice(pool_source)
    texte_de_la_question = verset_correct.get("text", "")
    
    options = set()
    reponse_correcte = ""

    # --- LOGIQUE EXPERTE ---
    
    # --- SCÉNARIO 1 : JEU SUR UN LIVRE SPÉCIFIQUE ---
    if is_specific_book:
        if request.difficulty == "facile": # Demande le chapitre
            reponse_correcte = f"{verset_correct.get('book_name')} {verset_correct.get('chapter')}"
            options.add(reponse_correcte)
            # 2 distracteurs du même livre, 1 d'un autre livre
            pool_pertinent = {f"{v.get('book_name')} {v.get('chapter')}" for v in pool_source if f"{v.get('book_name')} {v.get('chapter')}" != reponse_correcte}
            pool_general = {f"{v.get('book_name')} {v.get('chapter')}" for v in versets if v.get("book_name") != request.source_book}
            if len(pool_pertinent) >= 2: options.update(random.sample(list(pool_pertinent), 2))
            if len(options) < 4 and pool_general: options.add(random.choice(list(pool_general)))

        else: # Moyen et Difficile demandent la référence exacte
            reponse_correcte = f"{verset_correct.get('book_name')} {verset_correct.get('chapter')}:{verset_correct.get('verse')}"
            options.add(reponse_correcte)
            # Les distracteurs viennent tous du même livre
            pool_distracteurs = [v for v in pool_source if v != verset_correct]
            if len(pool_distracteurs) >= 3:
                for d in random.sample(pool_distracteurs, 3):
                    options.add(f"{d.get('book_name')} {d.get('chapter')}:{d.get('verse')}")
    
    # --- SCÉNARIO 2 : JEU SUR UNE GRANDE CATÉGORIE ---
    else:
        if request.difficulty == "facile": # Demande le livre
            reponse_correcte = verset_correct.get("book_name")
            options.add(reponse_correcte)
            # 2 distracteurs du même groupe, 1 hors groupe
            pool_pertinent = {v.get("book_name") for v in pool_source if v.get("book_name") != reponse_correcte}
            pool_general = {v.get("book_name") for v in versets if v.get("book_name", "").lower() not in source_book_names}
            if len(pool_pertinent) >= 2: options.update(random.sample(list(pool_pertinent), 2))
            if len(options) < 4 and pool_general: options.add(random.choice(list(pool_general)))

        elif request.difficulty == "moyen": # Demande le chapitre
            reponse_correcte = f"{verset_correct.get('book_name')} {verset_correct.get('chapter')}"
            options.add(reponse_correcte)
            # Les distracteurs viennent tous du même groupe
            pool_distracteurs = [v for v in pool_source if f"{v.get('book_name')} {v.get('chapter')}" != reponse_correcte]
            while len(options) < 4 and pool_distracteurs:
                d = random.choice(pool_distracteurs)
                options.add(f"{d.get('book_name')} {d.get('chapter')}")
                pool_distracteurs.remove(d)

        else: # Difficile, demande la référence exacte
            reponse_correcte = f"{verset_correct.get('book_name')} {verset_correct.get('chapter')}:{verset_correct.get('verse')}"
            options.add(reponse_correcte)
            # Les distracteurs viennent tous du même groupe, si possible même livre/chapitre
            distracteurs_pool = [v for v in pool_source if v != verset_correct]
            if len(distracteurs_pool) >= 3:
                for d in random.sample(distracteurs_pool, 3):
                    options.add(f"{d.get('book_name')} {d.get('chapter')}:{d.get('verse')}")

    # --- Assemblage final ---
    options_list = list(options)
    while len(options_list) < 4: # Fallback pour s'assurer qu'il y a toujours 4 options
        d = random.choice(versets)
        options_list.append(f"{d.get('book_name')} {d.get('chapter')}:{d.get('verse')}")
    random.shuffle(options_list)

    return {
        "question_text": texte_de_la_question,
        "options": options_list,
        "reponse_correcte": reponse_correcte
    }

@router.post("/qcm/random")
def jeu_qcm_aleatoire(data: ReferenceRequest):
    """
    Génère une question QCM à partir d'un verset choisi au hasard dans toute la Bible.
    """
    try:
        mots_utilises = set(data.mots_deja_utilises or [])
        
        verset_question = None
        indices_disponibles = []
        
        # On boucle jusqu'à trouver un verset avec des mots non utilisés
        tentatives = 0
        while not indices_disponibles and tentatives < 50:
            verset_question = random.choice(versets)
            if len(verset_question["text"].split()) >= 5:
                mots = verset_question["text"].split()
                mots_longs_indices = [i for i, mot in enumerate(mots) if len(mot) > 3]
                indices_disponibles = [i for i in mots_longs_indices if re.sub(r'[^\w\s-]', '', mots[i]).lower() not in mots_utilises]
            tentatives += 1

        if not indices_disponibles:
            return {"error": "Impossible de trouver un nouveau mot à mémoriser. Essayez de réinitialiser."}

        livre = verset_question.get("book_name", "Inconnu")
        mots = verset_question["text"].split()
        
        index_mot_a_retirer = random.choice(indices_disponibles)
        mot_a_retirer = mots[index_mot_a_retirer]
        mot_correct = re.sub(r'[^\w\s-]', '', mot_a_retirer)

        debut_contexte = max(0, index_mot_a_retirer - 3)
        partie_contexte = mots[debut_contexte:index_mot_a_retirer]
        contexte_pour_ia = " ".join(partie_contexte) + " _____"

        mauvais_mots = generer_mots_ia(contexte_pour_ia, mot_correct, livre)

        question_pour_flutter = verset_question["text"].replace(mot_a_retirer, "_____", 1)

        options = mauvais_mots + [mot_correct]
        random.shuffle(options)

        return {
            "question": question_pour_flutter,
            "options": options,
            "reponse_correcte": mot_correct
        }

    except Exception as e:
        print(f"Erreur interne inattendue dans /qcm/random: {e}")
        return {"error": f"Une erreur interne est survenue. Détail: {e}"}

@router.post("/remettre-en-ordre")
def get_unscrambled_verse_game(data: RemettreEnOrdreRequest):
    """
    Jeu de remise en ordre des mots d'un verset.
    """
    try:
        # Logique similaire aux autres jeux pour analyser la référence
        reference = data.reference.strip()
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

        if numeros_versets:
            versets_selectionnes = [v for v in versets if v.get("book_name", "").strip().lower() == livre.lower() and v.get("chapter") == chapitre and v.get("verse") in numeros_versets]
        else:
            versets_selectionnes = [v for v in versets if v.get("book_name", "").strip().lower() == livre.lower() and v.get("chapter") == chapitre]

        if not versets_selectionnes:
            return {"error": "Aucun verset trouvé pour cette référence."}

        # Choisir un verset au hasard
        verset_choisi = random.choice(versets_selectionnes)
        texte_original = verset_choisi["text"]
        
        # Séparer en mots et mélanger
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