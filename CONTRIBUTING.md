# Guide de Contribution - BovTemp

Merci de votre intérêt pour contribuer à BovTemp ! 🎉

## Comment Contribuer

### 1. Signaler un Bug

Créez une **GitHub Issue** avec :
- **Titre** : Description concise du problème
- **Description** : Étapes pour reproduire, résultat attendu, résultat réel
- **Environnement** : OS, version Python, version BovTemp
- **Logs** : Tout message d'erreur pertinent

**Exemple** :
```
Titre : Crash lors de l'export Excel avec plusieurs sites

Description :
Étapes :
1. Créer 2 sites
2. Ajouter 5 animaux par site
3. Cliquer "Export Excel"

Erreur :
UnicodeDecodeError: 'utf-8' codec can't decode byte...

Environnement :
- Windows 10
- Python 3.9.5
- BovTemp v5.0
```

### 2. Demander une Amélioration

Créez une **GitHub Issue** marquée `enhancement` avec :
- Fonctionnalité demandée
- Cas d'usage
- Exemple de comportement souhaité

**Exemple** :
```
Titre : Ajouter support CSV export

Description :
Actuellement, seul Excel est supporté. 
Un export CSV faciliterait l'intégration avec d'autres outils.

Cas d'usage : Importer les données dans R pour analyse statistique.
```

### 3. Soumettre du Code

#### Fork & Clone
```bash
# 1. Fork sur GitHub (bouton "Fork")
# 2. Clone votre fork
git clone https://github.com/votre-username/BovTemp.git
cd BovTemp

# 3. Ajouter remote original
git remote add upstream https://github.com/UIR/BovTemp.git
```

#### Créer une Branche
```bash
# Mettre à jour depuis main
git fetch upstream
git checkout main
git merge upstream/main

# Créer une branche pour votre feature
git checkout -b feature/nom-feature
# ou pour un bug fix
git checkout -b bugfix/description-bug
```

#### Conventions de Dénomination
```
feature/  - Nouvelle fonctionnalité
bugfix/   - Correction de bug
docs/     - Amélioration documentation
refactor/ - Refactorisation de code
test/     - Ajout de tests
```

#### Code Style

- **Indentation** : 4 espaces
- **Longueur de ligne** : ≤ 100 caractères
- **Encodage** : UTF-8
- **Commentaires** : Français, explicatifs

**Exemple bon style** :
```python
def get_animal_status(rfid: str, temp_c: float) -> dict:
    """
    Détermine l'état de santé d'un animal.
    
    Args:
        rfid: Identifiant RFID de l'animal
        temp_c: Température en Celsius
    
    Returns:
        dict: {"status": str, "alert": bool, "message": str}
    """
    if temp_c < TEMP_LOW:
        return {"status": "Hypothermie", "alert": True, "message": "Température anormale !"}
    elif temp_c <= TEMP_NORM:
        return {"status": "Normal", "alert": False, "message": ""}
    else:
        return {"status": "Fièvre", "alert": True, "message": "Traitement recommandé"}
```

#### Commits

Écrire des **commits clairs et atomiques** :

```bash
# ❌ Mauvais
git commit -m "Fixes et améliorations"
git commit -m "wip"

# ✅ Bon
git commit -m "Ajouter validation email avant enregistrement"
git commit -m "Corriger crash export Excel avec caractères spéciaux"
git commit -m "Documenter API base de données dans README"
```

Format recommandé :
```
<type>: <description brève (< 50 caractères)>

<explication optionnelle si nécessaire>

Fixes #123  (référence l'issue)
```

Types de commits :
- `feat:` Nouvelle fonctionnalité
- `fix:` Correction de bug
- `docs:` Documentation
- `refactor:` Refactorisation
- `test:` Ajout de tests
- `style:` Formatage, guillemets...
- `chore:` Maintenance, dépendances

### 4. Tester Localement

Avant de soumettre :

```bash
# Installer les dépendances dev
pip install -r requirements.txt

# Tester la fonctionnalité manuellement
python bovtemp_v5.py

# Vérifier la base de données
sqlite3 bovtemp.db ".tables"
```

### 5. Soumettre une Pull Request

```bash
# Pousser votre branche
git push origin feature/votre-feature
```

Créer une **Pull Request** sur GitHub avec :

**Titre** : `[court] Ajouter validation email` 

**Description** :
```markdown
## Description
Ajoute une validation d'email avant enregistrement pour éviter les erreurs SMTP.

## Type de changement
- [x] Correction de bug
- [ ] Nouvelle fonctionnalité
- [ ] Amélioration de documentation

## Changements
- Ajouter regex validation email
- Vérifier unicité avant insert DB
- Afficher message d'erreur utilisateur

## Tests effectués
- [x] Manuel : Registration avec emails valides/invalides
- [x] Base de données : Pas de doublons possibles
- [ ] Automatisé : Tests unitaires (future amélioration)

## Screenshots (si applicable)
Avant : [description]
Après : [description]

Fixes #42
```

**Template rapide** :
```
Titre : fix: corriger crash température > 45°C

Description :
Corrige IndexError lors de l'enregistrement de températures extrêmes.

Cause : Tableau color_map avait 44 éléments, pas 46.
Solution : Utiliser fonction interpolation au lieu d'index direct.
```

## Checklist Avant Soumettre

- [ ] Code testé localement
- [ ] Pas de fichiers secrets commités (`email_config.json`, etc.)
- [ ] `.gitignore` à jour si nouveaux fichiers temporaires
- [ ] Commit messages clairs et français
- [ ] Pas de fichiers `*.pyc`, `__pycache__`, etc.
- [ ] Documentation mise à jour (README, docstrings)
- [ ] Pas de code commenté laissé en arrière

## Process de Review

Un mainteneur va :
1. Vérifier le code qualité
2. Tester la fonctionnalité
3. Faire suggestions si nécessaire
4. Approuver et merger

Les suggestions ne sont pas des rejets, juste de l'itération ! 👍

## Questions ?

- 📧 Email : mawouena.fongbedji@uir.ac.ma
- 💬 Créer une **Discussion** sur GitHub
- 🐛 Chercher les **Issues existantes** évite les doublons

---

**Merci pour votre contribution !** 🙏

Votre travail aide à rendre BovTemp meilleur pour tous. `

