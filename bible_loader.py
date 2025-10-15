import json
import requests
from typing import List, Dict, Any, Optional
from functools import lru_cache
import re

class BibleLoader:
    """Gère le chargement des différentes versions de la Bible via API et fichiers locaux."""
    
    def __init__(self):
        self.bibles = {}
        self.api_base_url = "https://bible-api.com"
        self.load_local_bibles()
    
    def load_local_bibles(self):
        """Charge uniquement les fichiers JSON locaux disponibles."""
        versions = {
            "fr": "segond_1910.json",
            "en": "kjv.json",  # ← AJOUTÉ : Chargement du KJV local
        }
        
        for lang, filename in versions.items():
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    if "verses" in raw_data:
                        self.bibles[lang] = raw_data["verses"]
                        print(f"✅ {filename} chargé : {len(self.bibles[lang])} versets")
                    else:
                        print(f"⚠️  La clé 'verses' est introuvable dans {filename}")
                        self.bibles[lang] = []
            except FileNotFoundError:
                print(f"⚠️  Le fichier '{filename}' est introuvable.")
                self.bibles[lang] = []
            except json.JSONDecodeError:
                print(f"❌ Le fichier {filename} est mal formaté.")
                self.bibles[lang] = []
        
        # ← COMMENTÉ : Plus besoin de l'API externe maintenant
        # Marquer l'anglais comme disponible via API
        # self.bibles["en"] = "API"
        # print("✅ Anglais (KJV) disponible via bible-api.com")
    
    def get_verses(self, language: str = "fr") -> List[Dict[str, Any]]:
        """
        Retourne les versets pour la langue spécifiée.
        Pour l'anglais, retourne maintenant les versets du JSON local.
        """
        verses = self.bibles.get(language, self.bibles.get("fr", []))
        
        if verses == "API":
            return []  # Les versets anglais seront récupérés via l'API (ancien système)
        
        return verses
    
    def is_api_mode(self, language: str) -> bool:
        """Vérifie si une langue utilise l'API."""
        return self.bibles.get(language) == "API"
    
    @lru_cache(maxsize=2000)
    def fetch_verse_from_api(self, book: str, chapter: int, verse: int) -> Optional[Dict]:
        """
        Récupère un verset spécifique depuis l'API.
        Format de retour compatible avec votre structure JSON.
        """
        try:
            reference = f"{book} {chapter}:{verse}"
            url = f"{self.api_base_url}/{reference}?translation=kjv"
            
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if "text" in data:
                    return {
                        "book_name": book,
                        "chapter": chapter,
                        "verse": verse,
                        "text": data["text"].strip()
                    }
            
            return None
            
        except Exception as e:
            print(f"❌ Erreur API pour {book} {chapter}:{verse} - {e}")
            return None
    
    @lru_cache(maxsize=500)
    def fetch_chapter_from_api(self, book: str, chapter: int) -> List[Dict]:
        """
        Récupère un chapitre complet depuis l'API.
        Plus efficace que de récupérer verset par verset.
        """
        try:
            reference = f"{book} {chapter}"
            url = f"{self.api_base_url}/{reference}?translation=kjv"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                verses = []
                if "verses" in data:
                    for verse_data in data["verses"]:
                        verses.append({
                            "book_name": book,
                            "chapter": chapter,
                            "verse": verse_data["verse"],
                            "text": verse_data["text"].strip()
                        })
                
                return verses
            
            return []
            
        except Exception as e:
            print(f"❌ Erreur API pour {book} {chapter} - {e}")
            return []
    
    @lru_cache(maxsize=200)
    def fetch_passage_from_api(self, book: str, chapter: int, start_verse: int, end_verse: int) -> List[Dict]:
        """
        Récupère un passage (plusieurs versets) depuis l'API.
        """
        try:
            reference = f"{book} {chapter}:{start_verse}-{end_verse}"
            url = f"{self.api_base_url}/{reference}?translation=kjv"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                verses = []
                if "verses" in data:
                    for verse_data in data["verses"]:
                        verses.append({
                            "book_name": book,
                            "chapter": chapter,
                            "verse": verse_data["verse"],
                            "text": verse_data["text"].strip()
                        })
                
                return verses
            
            return []
            
        except Exception as e:
            print(f"❌ Erreur API pour {book} {chapter}:{start_verse}-{end_verse} - {e}")
            return []
    
    def get_verses_for_reference(self, reference: str, language: str = "fr") -> List[Dict]:
        """
        Récupère les versets pour une référence donnée.
        ← MODIFIÉ : Maintenant utilise le JSON local pour l'anglais aussi
        """
        if language == "fr":
            return self._get_from_local_json(reference, "fr")
        elif language == "en":
            # ← CHANGÉ : Utilise JSON local au lieu de l'API
            return self._get_from_local_json(reference, "en")
        
        return []
    
    def _get_from_local_json(self, reference: str, language: str = "fr") -> List[Dict]:
        """Récupère depuis le JSON local (français OU anglais)."""
        verses = self.get_verses(language)
        
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
                book = book.strip()
                chapter = int(chapter)
                verse = int(verse)
                
                found = [
                    v for v in verses
                    if v.get("book_name", "").strip().lower() == book.lower()
                    and int(v.get("chapter")) == chapter
                    and int(v.get("verse")) == verse
                ]
                return found
            
            match_chapitre = re.match(r"^(.*\D)\s*(\d+)$", reference.strip())
            if match_chapitre:
                book, chapter = match_chapitre.groups()
                book = book.strip()
                chapter = int(chapter)
                
                return [
                    v for v in verses
                    if v.get("book_name", "").strip().lower() == book.lower()
                    and int(v.get("chapter")) == chapter
                ]
            
        except Exception as e:
            print(f"Erreur parsing référence locale: {e}")
        
        return []
    
    def _get_from_api(self, reference: str) -> List[Dict]:
        """Récupère depuis l'API (anglais) - ANCIEN SYSTÈME, conservé pour backup."""
        try:
            match_plage = re.match(r"^(.*\D)\s*(\d+):(\d+)-(\d+)$", reference.strip())
            
            if match_plage:
                book, chapter, start_v, end_v = match_plage.groups()
                return self.fetch_passage_from_api(
                    book.strip(), int(chapter), int(start_v), int(end_v)
                )
            
            match_unique = re.match(r"^(.*\D)\s*(\d+):(\d+)$", reference.strip())
            if match_unique:
                book, chapter, verse = match_unique.groups()
                result = self.fetch_verse_from_api(book.strip(), int(chapter), int(verse))
                return [result] if result else []
            
            match_chapitre = re.match(r"^(.*\D)\s*(\d+)$", reference.strip())
            if match_chapitre:
                book, chapter = match_chapitre.groups()
                return self.fetch_chapter_from_api(book.strip(), int(chapter))
            
        except Exception as e:
            print(f"Erreur parsing référence API: {e}")
        
        return []

# Instance globale
bible_loader = BibleLoader()