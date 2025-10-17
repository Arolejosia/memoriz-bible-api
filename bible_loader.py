import json
import requests
from typing import List, Dict, Any, Optional
from functools import lru_cache
import re

class BibleLoader:
    """Gère le chargement des différentes versions de la Bible via fichiers locaux."""
    
    def __init__(self):
        self.bibles = {}
        self.load_local_bibles()
    
    def load_local_bibles(self):
        """Charge les fichiers JSON locaux disponibles (FR et EN)."""
        versions = {
            "fr": "segond_1910.json",
            "en": "kjv.json",
        }
        
        for lang, filename in versions.items():
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    
                    # ✅ Support des deux formats possibles
                    if "verses" in raw_data:
                        self.bibles[lang] = raw_data["verses"]
                    elif isinstance(raw_data, list):
                        self.bibles[lang] = raw_data
                    else:
                        print(f"⚠️  Format non reconnu dans {filename}")
                        self.bibles[lang] = []
                    
                    print(f"✅ {filename} chargé : {len(self.bibles[lang])} versets")
                    
            except FileNotFoundError:
                print(f"⚠️  Le fichier '{filename}' est introuvable.")
                self.bibles[lang] = []
            except json.JSONDecodeError as e:
                print(f"❌ Le fichier {filename} est mal formaté: {e}")
                self.bibles[lang] = []
    
    def get_verses(self, language: str = "fr") -> List[Dict[str, Any]]:
        """
        Retourne les versets pour la langue spécifiée.
        Supporte maintenant FR et EN via JSON local.
        """
        verses = self.bibles.get(language, self.bibles.get("fr", []))
        
        if not isinstance(verses, list):
            return []
        
        return verses
    
    def is_api_mode(self, language: str) -> bool:
        """
        Vérifie si une langue utilise l'API.
        ✅ CORRECTION: Toujours False maintenant (tout en local)
        """
        return False
    
    def get_verses_for_reference(self, reference: str, language: str = "fr") -> List[Dict]:
        """
        Récupère les versets pour une référence donnée.
        ✅ Supporte français ET anglais via JSON local
        """
        return self._get_from_local_json(reference, language)
    
    def _get_from_local_json(self, reference: str, language: str = "fr") -> List[Dict]:
        """
        Récupère depuis le JSON local (français ou anglais).
        Gère les différents formats de référence : 
        - "Jean 3:16"
        - "Jean 3:16-18" 
        - "Jean 3"
        """
        verses = self.get_verses(language)
        
        if not verses:
            print(f"⚠️  Aucun verset disponible pour la langue '{language}'")
            return []
        
        try:
            # Pattern 1: Plage de versets (ex: Jean 3:16-18)
            match_plage = re.match(r"^(.*\D)\s*(\d+):(\d+)-(\d+)$", reference.strip())
            
            if match_plage:
                book, chapter, start_v, end_v = match_plage.groups()
                book = book.strip()
                chapter = int(chapter)
                verse_nums = list(range(int(start_v), int(end_v) + 1))
                
                found = [
                    v for v in verses
                    if self._normalize_book(v.get("book_name", "")) == self._normalize_book(book)
                    and int(v.get("chapter", 0)) == chapter
                    and int(v.get("verse", 0)) in verse_nums
                ]
                
                if found:
                    print(f"✅ Trouvé {len(found)} versets pour '{reference}' en {language}")
                return found
            
            # Pattern 2: Verset unique (ex: Jean 3:16)
            match_unique = re.match(r"^(.*\D)\s*(\d+):(\d+)$", reference.strip())
            if match_unique:
                book, chapter, verse = match_unique.groups()
                book = book.strip()
                chapter = int(chapter)
                verse = int(verse)
                
                found = [
                    v for v in verses
                    if self._normalize_book(v.get("book_name", "")) == self._normalize_book(book)
                    and int(v.get("chapter", 0)) == chapter
                    and int(v.get("verse", 0)) == verse
                ]
                
                if found:
                    print(f"✅ Trouvé verset '{reference}' en {language}")
                else:
                    print(f"⚠️  Verset '{reference}' non trouvé en {language}")
                    print(f"   Livre recherché: '{self._normalize_book(book)}'")
                
                return found
            
            # Pattern 3: Chapitre entier (ex: Jean 3)
            match_chapitre = re.match(r"^(.*\D)\s*(\d+)$", reference.strip())
            if match_chapitre:
                book, chapter = match_chapitre.groups()
                book = book.strip()
                chapter = int(chapter)
                
                found = [
                    v for v in verses
                    if self._normalize_book(v.get("book_name", "")) == self._normalize_book(book)
                    and int(v.get("chapter", 0)) == chapter
                ]
                
                if found:
                    print(f"✅ Trouvé {len(found)} versets pour chapitre '{reference}' en {language}")
                return found
            
            print(f"❌ Format de référence non reconnu: '{reference}'")
            
        except Exception as e:
            print(f"❌ Erreur parsing référence '{reference}': {e}")
        
        return []
    
    def _normalize_book(self, book_name: str) -> str:
        """
        Normalise le nom d'un livre pour la comparaison.
        Gère les différences de casse et espaces.
        """
        return book_name.strip().lower()

# Instance globale
bible_loader = BibleLoader()