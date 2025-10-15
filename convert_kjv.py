# convert_kjv.py
import json

print("🔄 Chargement du fichier KJV...")

with open('kjv.json', 'r', encoding='utf-8') as f:
    kjv_data = json.load(f)

print(f"✅ Fichier chargé : {kjv_data['translation']}")

verses = []

for book in kjv_data['books']:
    book_name = book['name']
    print(f"📖 Traitement de {book_name}...")
    
    for chapter in book['chapters']:
        chapter_num = chapter['chapter']
        
        for verse in chapter['verses']:
            verses.append({
                "book_name": book_name,
                "chapter": chapter_num,
                "verse": verse['verse'],
                "text": verse['text']
            })

print(f"\n✅ {len(verses)} versets convertis")

# Sauvegarder au nouveau format
output = {"verses": verses}

with open('kjv_flat.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("✅ Fichier sauvegardé : kjv_flat.json")
print("\n🎯 Prochaines étapes :")
print("   1. Renommez 'kjv.json' en 'kjv_original.json' (backup)")
print("   2. Renommez 'kjv_flat.json' en 'kjv.json'")
print("   3. Redémarrez votre API")