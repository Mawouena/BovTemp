# BovTemp v5 - Plateforme Intégrée de Gestion d'Élevage

Une application de gestion complète pour l'élevage de bovins, ovins, caprins et équins avec support RFID, suivi de santé, alimentation et données généalogiques.

## Caractéristiques

### 🐄 Gestion d'Animaux
- Suivi des bovins, ovins, caprins et équins
- Nécessaire sous-catégories de races
- Données généalogiques (parents, grands-parents)
- Date d'arrivée, poids, statut d'élevage

### 🌡️ Suivi de Santé
- **Relevé de température** (Celsius/Fahrenheit)
- **Détection d'état** : Normal, En chaleur, Fièvre, Hypothermie
- **Gestion des traitements** : Posologie, durée, notes
- **Calendrier de vaccinations** : Par espèce
- **Suivi de gestation** : Date de saillie, naissances attendues/réelles

### 🍽️ Gestion Alimentaire
- Suivi des repas et rations
- Types d'aliments : Foin, Ensilage, Concentré, etc.
- Quantités et unités personnalisables

### 📊 Rapports & Exports
- **Graphiques** : Évolution de température, données temporelles
- **Export Excel** : Listes d'animaux, données de traitements, rapports détaillés
- **Historique complet** : SQLite avec logs système

### 🔌 Connectivité
- **Support RFID** : Lecture via port série (COM/USB)
- **Notifications par email** : Alertes de santé et d'événements
- **Configuration SMTP** : Gmail, Outlook, serveurs personnalisés

### 👥 Multi-utilisateurs
- Authentification par email/mot de passe
- Rôles utilisateur (Admin, User)
- Gestion des sites/fermes multiples
- Informations personnellees protégées

### 🎨 Interface
- Design inspiré **Mikyas Studio**
- Thème clair avec palette de couleurs cohérente
- Boutons colorés (pill-buttons)
- Interface tactile-friendly

## Installation

### Prérequis
- Python 3.8+
- pip (gestionnaire de paquets Python)

### Étapes d'installation

1. **Cloner le dépôt**
```bash
git clone https://github.com/votre-username/BovTemp.git
cd BovTemp
```

2. **Créer un environnement virtuel** (recommandé)
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

4. **Configurer les paramètres** (optionnel)
- Éditer `bovtemp_cfg.json` pour les préférences générales
- Éditer `email_config.json` pour activer les notifications email

5. **Lancer l'application**
```bash
python bovtemp_v5.py
```

## Configuration

### email_config.json
Pour activer les notifications email, configurez :
```json
{
  "smtp": "smtp.gmail.com",
  "port": "587",
  "user": "votre@email.com",
  "password": "votre_mot_de_passe_app",
  "to": "email_notification@example.com",
  "enabled": false
}
```

**⚠️ Sécurité** : Utilisez des **mots de passe d'application** (pas vos vrais mots de passe) pour les comptes Gmail et autres services.

### bovtemp_cfg.json
```json
{
  "email": "admin@uir.com",
  "theme": "light"
}
```

## Utilisation

### Première Connexion
1. Cliquez sur **"Créer un compte"**
2. Renseignez vos informations (Nom, Prénom, Email, Téléphone)
3. Définissez un mot de passe sécurité
4. Connectez-vous

### Ajouter un Site/Ferme
1. Menu **Back-office** → **Gestion des Sites**
2. Cliquez **Ajouter un Site**
3. Renseignez nom, adresse, ville

### Ajouter un Animal
1. Sélectionnez un site
2. Cliquez **Acquérir**
3. Scannez le tag RFID ou saisissez le numéro RFID
4. Complétez les informations (nom, race, sexe, etc.)

### Enregistrer une Température
1. Cliquez **Lecture** (icône thermomètre)
2. Scannez le tag RFID
3. La température est enregistrée automatiquement

### Exporter un Rapport Excel
1. Menu **Rapports** → **Export Excel**
2. Sélectionnez les données à exporter
3. Choisissez l'emplacement de sauvegarde

## Structure du Projet

```
BovTemp/
├── bovtemp_v5.py              # Application principale
├── bovtemp_cfg.json            # Configuration générale
├── email_config.json            # Configuration email
├── cattle_db.json               # Données de référence
├── imagesDb/                    # Dossier pour images d'animaux
├── LED/
│   └── LED.ino                  # Firmware Arduino pour alertes LED
├── requirements.txt             # Dépendances Python
├── README.md                    # Ce fichier
├── LICENSE                      # Licence du projet
└── bovtemp.db                   # Base de données (généré)
```

## Dépendances Principales

| Package | Utilisation |
|---------|-------------|
| **tkinter** | Interface graphique |
| **sqlite3** | Base de données |
| **matplotlib** | Graphiques |
| **openpyxl** | Export Excel |
| **pyserial** | Lecture port série RFID |
| **smtplib** | Notifications email |

> Note : Tkinter est généralement inclus avec Python. Pour les autres, utilisez `pip install -r requirements.txt`

## Matériel Supporté

### Lecteur RFID
- Lecteur série compatible RFID (CH340, PL2303, etc.)
- Connexion COM directe sur le PC
- Baudrate : 9600 (configurable)

### Arduino/Alertes
- Firmware disponible dans `LED/LED.ino`
- Interface pour alertes visuelles/sonores

## Architecture

### Classes Principales

- **DB** : Gestion SQLite (migrations, requêtes)
- **App** : Fenêtre principale Tkinter
- **FrameLogin** : Écran d'authentification
- **FrameHome** : Accueil avec boutons d'action (ImageButtons)
- **FrameAnimal** : Détails et gestion d'un animal
- **FrameBackOffice** : Gestion administrateur

### Base de Données

Tables principales :
- `users` : Authentification
- `sites` : Fermes/élevages
- `animals` : Animaux
- `temps` : Historique température
- `traitements` : Suivis médicaux
- `vaccinations` : Calendrier vaccinal
- `gestations` : Suivi de reproduction
- `alimentation` : Rations et repas
- `notifs` : Historique notifications

## Sécurité

- ✅ Hash PBKDF2 pour les mots de passe (100 000 itérations)
- ✅ Sel aléatoire par utilisateur
- ✅ Isolation des données par utilisateur (multi-tenant)
- ⚠️ Fichiers sensibles : Ne pas committer `email_config.json` en production (ajouté à `.gitignore`)

## Support RFID & Série

L'application supporte :
- Lecteurs RFID standard sur port COM
- **Windows** : COM1, COM2, COM3... (détection automatique)
- **Linux** : /dev/ttyUSB0, /dev/ttyACM0...
- **Mac** : /dev/tty.usbserial...

Configuration dans l'interface → **Paramètres** → **Port Série**

## Graphiques & Rapports

- Graphiques matplotlib TkAgg (temps réel)
- Export Excel multisheet avec formatage
- Compatibilité : Excel 2010+

## Performance

- Base SQLite optimisée avec indexes
- Threading pour opérations longues (email, export)
- Gestion des ressources (fermeture connexions DB)

## Limitations et Améliorations Futures

- [ ] Interface web (Flask/Django)
- [ ] Synchronisation cloud
- [ ] App mobile native
- [ ] Prédictions IA (santé animale)
- [ ] Intégration caméras de surveillance

## Contribution

Les contributions sont bienvenues ! Veuillez :
1. Fork le dépôt
2. Créer une branche (`git checkout -b feature/amélioration`)
3. Committer les changements (`git commit -m 'Ajouter amélioration'`)
4. Pousser vers la branche (`git push origin feature/amélioration`)
5. Ouvrir une Pull Request

## Licence

Ce projet est sous licence **MIT** - voir [LICENSE](LICENSE) pour les détails.

## Auteur

Développé pour **UIR** (Institut de l'Université Royale)
- Chercheur responsable : **Charoub**
- Plateforme d'élevage intégré

## Support & Contact

Pour les bugs, questions ou suggestions :
- 📧 Email : mawouena.fongbedji@uir.ac.ma
- 📋 Issues : [GitHub Issues](https://github.com/votre-username/BovTemp/issues)

---

**Version** : 5.0  
**Mise à jour** : Avril 2026  
**Python** : 3.8+  
**Statut** : Actif
