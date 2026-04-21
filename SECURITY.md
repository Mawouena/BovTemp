# Gérer la Sécurité de BovTemp

## ⚠️ Fichiers Sensibles

Ne **JAMAIS** committer les fichiers suivants contenant des secrets :

```
email_config.json    (contient credentials SMTP)
bovtemp_cfg.json     (peut contenir données personnelles)
cattle_db.json       (données référence sensibles)
*.db                 (base de données avec données réelles)
```

## 📋 Avant de Publier sur GitHub

### 1. Nettoyer les Secrets

```bash
# Vérifier les fichiers qui seraient commités
git status

# Supprimer les fichiers sensibles du repo (s'ils existent)
git rm --cached email_config.json
git rm --cached bovtemp_cfg.json
```

### 2. Créer des Fichiers Template

Créer des exemples sans vraies données :

**email_config.example.json**
```json
{
  "smtp": "smtp.gmail.com",
  "port": "587",
  "user": "votre@email.com",
  "password": "votre_mot_de_passe_app",
  "to": "notification@example.com",
  "enabled": false
}
```

**bovtemp_cfg.example.json**
```json
{
  "email": "admin@example.com",
  "theme": "light"
}
```

### 3. Documenter dans le README

Créer les fichiers de config localement :

```bash
cp email_config.example.json email_config.json
cp bovtemp_cfg.example.json bovtemp_cfg.json
# Éditer avec vos vraies données
```

## 🔐 Bonnes Pratiques

### Avec Email Gmail
- ❌ Non : Votre mot de passe Gmail
- ✅ Oui : **App Password** (mot de passe d'application)
  
Générer une App Password :
1. Aller sur [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Sélectionner "Mail" et "Windows" (ou votre OS)
3. Copier le mot de passe généré
4. L'utiliser dans `email_config.json`

### Base de Données
- Changer les chemins de DB si nécessaire
- Ne pas exposer la DB de production
- Utiliser `.gitignore` pour `*.db`

### Variables d'Environnement (Optionnel)

Pour une sécurité accrue, utiliser des variables d'environ :

```python
import os
email_user = os.environ.get('BOVTEMP_EMAIL_USER')
email_password = os.environ.get('BOVTEMP_EMAIL_PASSWORD')
```

Puis dans le shell :
```bash
export BOVTEMP_EMAIL_USER="votre@email.com"
export BOVTEMP_EMAIL_PASSWORD="app_password"
python bovtemp_v5.py
```

## 🔄 Processus de Déploiement

1. ✅ Vérifier `.gitignore` inclut les secrets
2. ✅ Modifier `email_config.json` (supprimer mot de passe réel)
3. ✅ Créer `.example.json` avec modèle
4. ✅ Vérifier pas de secrets dans les commits
5. ✅ Publier sur GitHub

## 📊 Vérifier les Secrets

```bash
# Chercher mots de passe dans les fichiers
grep -r "password" . --include="*.json" --include="*.py"
grep -r "secret" . --include="*.json" --include="*.py"

# Vérifier les credentials ne sont pas en clair
git log -p | grep -i "password\|secret\|api_key"
```

## Si les Secrets Ont Été Exposés

1. **Changer les mots de passe immédiatement**
2. **Supprimer de l'historique Git** :
   ```bash
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch email_config.json' \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. **Force push** (attention - réécrit l'historique) :
   ```bash
   git push origin --force --all
   ```

---

**Rappelez-vous** : La sécurité est une responsabilité partagée. Activez l'authentification 2FA sur les comptes sensibles ! 🔐
