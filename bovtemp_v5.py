#!/usr/bin/env python3
"""
BovTemp v5 — Plateforme intégrée d'élevage
Design inspiré Mikyas Studio : topbar pill-buttons, sidebar structurée, zone principale
Nouvelles fonctionnalités : suivi grossesse, alimentation, traitements détaillés,
sous-catégories de races, back-office complet, écran d'accueil avec ImageButtons
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3, hashlib, secrets, os, json, threading, sys, random, re, queue
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, date
import calendar

try:
    import winsound
    WINSOUND_OK = True
except ImportError:
    WINSOUND_OK = False

try:
    import serial, serial.tools.list_ports
    SERIAL_OK = True
except ImportError:
    SERIAL_OK = False

try:
    import matplotlib; matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.dates as mdates
    MPLOT = True
except Exception:
    MPLOT = False

try:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    XLSX_OK = True
except ImportError:
    XLSX_OK = False

# ══════════════════════════════════════════════════════════════════════════════
#  PALETTE — Mikyas-inspired : gris clair, blanc, boutons colorés
# ══════════════════════════════════════════════════════════════════════════════
PAL = dict(
    bg="#F0F1F3",          # fond général gris clair
    bg_main="#FFFFFF",     # zone principale blanche
    bg_sidebar="#E8EAED",  # sidebar légèrement plus sombre
    bg_card="#FFFFFF",
    bg_input="#FFFFFF",
    bg_sect="#F5F6F8",
    bg_header="#2C2C2C",   # topbar sombre comme Mikyas
    text="#1A1A1A",
    text_sub="#555555",
    text_light="#888888",
    border="#D0D3D8",
    border_dark="#BABEC6",

    # Boutons pill colorés (style Mikyas)
    btn_green="#2ECC71",   # Acquérir
    btn_blue="#3498DB",    # Graphique
    btn_purple="#8E44AD",  # Tableau
    btn_teal="#1ABC9C",    # Sauvegarder
    btn_orange="#E67E22",  # Alertes
    btn_red="#E74C3C",     # Supprimer
    btn_gray="#95A5A6",    # Secondaire
    btn_connect="#27AE60", # Se connecter

    # États bêtes
    stable="#27AE60",      # vert
    instable="#E74C3C",    # rouge
    traitement="#E67E22",  # orange

    accent="#3498DB",
    topbar_text="#FFFFFF",
    topbar_sub="#AAAAAA",

    live_bg="#EAFAF1",
    live_fg="#1E8449",
)

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTES MÉTIER
# ══════════════════════════════════════════════════════════════════════════════
SOUS_CATEGORIES = {
    "bovin": ["Vache laitière","Bovin viande","Bovin mixte","Veau","Taureau","Génisse","Autre"],
    "ovin":  ["Brebis laitière","Ovin viande","Agneau","Bélier","Antenaise","Autre"],
    "caprin":["Chèvre laitière","Caprin viande","Chevreau","Bouc","Autre"],
    "equin": ["Cheval de sport","Cheval de trait","Poney","Jument","Étalon","Poulinière","Autre"],
}

ESPECE_ICON  = {"bovin":"🐄","ovin":"🐑","caprin":"🐐","equin":"🐴"}
ESPECE_LABEL = {"bovin":"Bovins","ovin":"Ovins","caprin":"Caprins","equin":"Équins"}

VACCINS_DB = {
    "bovin":  ["IBR","BVD","BRSV","PI3","Leptospirose","Clostridiose","Fièvre aphteuse","Brucellose","Pasteurellose"],
    "ovin":   ["Clostridiose","Fièvre catarrhale","Pasteurellose","Entérotoxémie","Brucellose"],
    "caprin": ["Clostridiose","Artérite","Agalactie","CAE","Pasteurellose"],
    "equin":  ["Grippe équine","Tétanos","Rhinopneumonie","West Nile","Rotavirus"],
}
TRAITEMENTS_DB = ["Antibiotique","Antiparasitaire","Antifongique","Anti-inflammatoire",
                   "Vitamines","Minéraux","Probiotiques","Autre"]
POSOLOGIES_DB  = ["1x/jour","2x/jour","3x/jour","1x/semaine","1x/mois","Dose unique","Autre"]
DUREES_DB      = ["1 jour","3 jours","5 jours","7 jours","10 jours","14 jours","21 jours","1 mois","Autre"]

ALIMENTS_DB    = ["Foin","Ensilage","Concentré","Granulés","Minéraux","Sel","Eau","Pâturage","Autre"]
UNITES_DB      = ["kg","g","L","portions","boisseaux"]

TEMP_LOW=37.5; TEMP_NORM=39.5; TEMP_CHALEUR=40.0; TEMP_HIGH=40.5

def f2c(f): return (float(f)-32)*5/9
def c2f(c): return float(c)*9/5+32

def get_status(tc, sexe="M"):
    if tc is None: return "—"
    if tc < TEMP_LOW:    return "Hypothermie"
    if tc <= TEMP_NORM:  return "Normal"
    if tc <= TEMP_CHALEUR and str(sexe).upper()=="F": return "En chaleur"
    if tc <= TEMP_HIGH:  return "Elevee"
    return "Fievre"

def hash_pwd(p, s=None):
    if not s: s = secrets.token_hex(16)
    return hashlib.pbkdf2_hmac("sha256", p.encode(), s.encode(), 100000).hex(), s

def check_pwd(p, h, s): return hash_pwd(p, s)[0] == h

_CFG = "bovtemp_cfg.json"
def _load_cfg(): return json.load(open(_CFG)) if os.path.exists(_CFG) else {}
def _save_cfg(d): json.dump(d, open(_CFG,"w"), indent=2)

# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════════════════════
class DB:
    def __init__(self, path="bovtemp.db"):
        self.cx = sqlite3.connect(path, check_same_thread=False)
        self.cx.row_factory = sqlite3.Row
        self.cx.execute("PRAGMA foreign_keys=ON")
        self._lk = threading.Lock()
        self._init()
        self._migrate()

    def _q(self, sql, a=()): return self.cx.execute(sql, a)
    def _w(self, sql, a=()):
        with self._lk: self.cx.execute(sql, a); self.cx.commit()

    def _migrate(self):
        """Ajoute les colonnes manquantes sur les anciennes bases de données."""
        migrations = [
            ("animals",  "sous_categorie",     "TEXT DEFAULT ''"),
            ("animals",  "date_arrivee",        "TEXT DEFAULT ''"),
            ("animals",  "poids",               "REAL DEFAULT 0"),
            ("animals",  "statut_etat",         "TEXT DEFAULT 'stable'"),
            ("animals",  "actif",               "INTEGER DEFAULT 1"),
            ("users",    "role",                "TEXT DEFAULT 'user'"),
            ("sites",    "notes",               "TEXT DEFAULT ''"),
        ]
        # Nouvelles tables entières
        new_tables = {
            "traitements": """CREATE TABLE IF NOT EXISTS traitements(
                id INTEGER PRIMARY KEY, rfid TEXT, site_id INTEGER,
                date_traitement TEXT, traitement TEXT, posologie TEXT, duree TEXT,
                notes TEXT DEFAULT '', ts TEXT DEFAULT CURRENT_TIMESTAMP)""",
            "vaccinations": """CREATE TABLE IF NOT EXISTS vaccinations(
                id INTEGER PRIMARY KEY, rfid TEXT, site_id INTEGER,
                date_vaccin TEXT, vaccin TEXT, posologie TEXT, duree TEXT,
                notes TEXT DEFAULT '', ts TEXT DEFAULT CURRENT_TIMESTAMP)""",
            "gestations": """CREATE TABLE IF NOT EXISTS gestations(
                id INTEGER PRIMARY KEY, rfid TEXT, site_id INTEGER,
                date_saillie TEXT, date_naissance_prevue TEXT,
                date_naissance_reelle TEXT DEFAULT '',
                nb_petits INTEGER DEFAULT 1, poids_naissance REAL DEFAULT 0,
                notes TEXT DEFAULT '', statut TEXT DEFAULT 'en_cours',
                ts TEXT DEFAULT CURRENT_TIMESTAMP)""",
            "alimentation": """CREATE TABLE IF NOT EXISTS alimentation(
                id INTEGER PRIMARY KEY, rfid TEXT, site_id INTEGER,
                date_repas TEXT, aliment TEXT, quantite REAL, unite TEXT,
                notes TEXT DEFAULT '', ts TEXT DEFAULT CURRENT_TIMESTAMP)""",
            "vaccins_ref": """CREATE TABLE IF NOT EXISTS vaccins_ref(
                id INTEGER PRIMARY KEY, nom TEXT UNIQUE, espece TEXT DEFAULT '')""",
            "traitements_ref": """CREATE TABLE IF NOT EXISTS traitements_ref(
                id INTEGER PRIMARY KEY, nom TEXT UNIQUE)""",
            "aliments_ref": """CREATE TABLE IF NOT EXISTS aliments_ref(
                id INTEGER PRIMARY KEY, nom TEXT UNIQUE)""",
        }
        # Créer les nouvelles tables si elles n'existent pas
        for tbl, ddl in new_tables.items():
            try:
                self.cx.execute(ddl)
            except Exception:
                pass
        self.cx.commit()
        # Ajouter les colonnes manquantes
        for table, col, coldef in migrations:
            try:
                self.cx.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coldef}")
                self.cx.commit()
            except Exception:
                pass  # La colonne existe déjà

    def _init(self):
        self.cx.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, nom TEXT, prenom TEXT,
            email TEXT UNIQUE NOT NULL, telephone TEXT, role TEXT DEFAULT 'user',
            hash TEXT, salt TEXT, reset_code TEXT,
            created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS sites(
            id INTEGER PRIMARY KEY, uid INTEGER NOT NULL,
            nom TEXT, adresse TEXT, ville TEXT, pays TEXT DEFAULT 'France',
            especes TEXT DEFAULT '[]', nb_tetes INTEGER DEFAULT 0, notes TEXT,
            created TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(uid) REFERENCES users(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS animals(
            id INTEGER PRIMARY KEY, site_id INTEGER NOT NULL,
            rfid TEXT UNIQUE, nom TEXT, espece TEXT, sous_categorie TEXT DEFAULT '',
            race TEXT, sexe TEXT DEFAULT 'F', dob TEXT, date_arrivee TEXT DEFAULT '',
            poids REAL DEFAULT 0, enclos TEXT DEFAULT '',
            pere TEXT DEFAULT '', mere TEXT DEFAULT '',
            gp_pm TEXT DEFAULT '', gp_pf TEXT DEFAULT '',
            gp_mm TEXT DEFAULT '', gp_mf TEXT DEFAULT '',
            notes TEXT DEFAULT '', vaccins TEXT DEFAULT '[]',
            acquisition INTEGER DEFAULT 0, statut_etat TEXT DEFAULT 'stable',
            actif INTEGER DEFAULT 1,
            created TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS temps(
            id INTEGER PRIMARY KEY, rfid TEXT, site_id INTEGER,
            tc REAL, tf REAL, statut TEXT,
            ts TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS traitements(
            id INTEGER PRIMARY KEY, rfid TEXT, site_id INTEGER,
            date_traitement TEXT, traitement TEXT, posologie TEXT, duree TEXT,
            notes TEXT DEFAULT '',
            ts TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS vaccinations(
            id INTEGER PRIMARY KEY, rfid TEXT, site_id INTEGER,
            date_vaccin TEXT, vaccin TEXT, posologie TEXT, duree TEXT,
            notes TEXT DEFAULT '',
            ts TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS gestations(
            id INTEGER PRIMARY KEY, rfid TEXT, site_id INTEGER,
            date_saillie TEXT, date_naissance_prevue TEXT, date_naissance_reelle TEXT DEFAULT '',
            nb_petits INTEGER DEFAULT 1, poids_naissance REAL DEFAULT 0,
            notes TEXT DEFAULT '', statut TEXT DEFAULT 'en_cours',
            ts TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS alimentation(
            id INTEGER PRIMARY KEY, rfid TEXT, site_id INTEGER,
            date_repas TEXT, aliment TEXT, quantite REAL, unite TEXT,
            notes TEXT DEFAULT '',
            ts TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS notifs(
            id INTEGER PRIMARY KEY, uid INTEGER,
            msg TEXT, type TEXT DEFAULT 'info', read INTEGER DEFAULT 0,
            rfid TEXT DEFAULT '', site_id INTEGER DEFAULT 0,
            ts TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS email_cfg(
            id INTEGER PRIMARY KEY, uid INTEGER UNIQUE,
            smtp TEXT DEFAULT 'smtp.gmail.com', port TEXT DEFAULT '587',
            user TEXT DEFAULT '', password TEXT DEFAULT '',
            dest TEXT DEFAULT '', enabled INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS serial_cfg(
            id INTEGER PRIMARY KEY, uid INTEGER UNIQUE,
            port TEXT DEFAULT '', baudrate TEXT DEFAULT '9600', active INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS enclos(
            id INTEGER PRIMARY KEY, site_id INTEGER NOT NULL, nom TEXT NOT NULL,
            FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS vaccins_ref(
            id INTEGER PRIMARY KEY, nom TEXT UNIQUE, espece TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS traitements_ref(
            id INTEGER PRIMARY KEY, nom TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS aliments_ref(
            id INTEGER PRIMARY KEY, nom TEXT UNIQUE);
        """); self.cx.commit()

    # ── Users ─────────────────────────────────────────────────────────────────
    def reg(self, nom, prenom, email, tel, pwd, role="user"):
        h, s = hash_pwd(pwd)
        try:
            self._w("INSERT INTO users(nom,prenom,email,telephone,hash,salt,role) VALUES(?,?,?,?,?,?,?)",
                    (nom, prenom, email.lower().strip(), tel, h, s, role))
            return True, ""
        except sqlite3.IntegrityError:
            return False, "Cet email est déjà utilisé."

    def login(self, email, pwd):
        r = self._q("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
        if r and check_pwd(pwd, r["hash"], r["salt"]): return dict(r)
        return None

    def email_exists(self, email):
        return bool(self._q("SELECT 1 FROM users WHERE email=?", (email.lower().strip(),)).fetchone())

    def get_user(self, uid):
        r = self._q("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        return dict(r) if r else None

    def get_all_users(self):
        return [dict(r) for r in self._q("SELECT * FROM users ORDER BY nom").fetchall()]

    def upd_user(self, uid, **kw):
        self._w(f"UPDATE users SET {','.join(f'{k}=?' for k in kw)} WHERE id=?",
                list(kw.values()) + [uid])

    def del_user(self, uid):
        self._w("DELETE FROM users WHERE id=?", (uid,))

    def set_code(self, email, code):
        self._w("UPDATE users SET reset_code=? WHERE email=?", (code, email))

    def reset_pwd(self, email, code, new_pwd):
        r = self._q("SELECT reset_code FROM users WHERE email=?", (email,)).fetchone()
        if not r or r["reset_code"] != code: return False
        h, s = hash_pwd(new_pwd)
        self._w("UPDATE users SET hash=?,salt=?,reset_code=NULL WHERE email=?", (h, s, email))
        return True

    # ── Sites ─────────────────────────────────────────────────────────────────
    def add_site(self, uid, nom, adresse, ville, pays, especes, nb, notes=""):
        with self._lk:
            self.cx.execute(
                "INSERT INTO sites(uid,nom,adresse,ville,pays,especes,nb_tetes,notes) VALUES(?,?,?,?,?,?,?,?)",
                (uid, nom, adresse, ville, pays, json.dumps(especes), nb, notes))
            self.cx.commit()
            return self.cx.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_sites(self, uid):
        out = []
        for r in self._q("SELECT * FROM sites WHERE uid=? ORDER BY nom", (uid,)).fetchall():
            d = dict(r); d["especes"] = json.loads(d["especes"] or "[]")
            d["animal_count"] = self._q("SELECT COUNT(*) FROM animals WHERE site_id=?", (d["id"],)).fetchone()[0]
            d["acq_count"] = self._q("SELECT COUNT(*) FROM animals WHERE site_id=? AND acquisition=1", (d["id"],)).fetchone()[0]
            out.append(d)
        return out

    def get_site(self, sid):
        r = self._q("SELECT * FROM sites WHERE id=?", (sid,)).fetchone()
        if not r: return None
        d = dict(r); d["especes"] = json.loads(d["especes"] or "[]")
        return d

    def upd_site(self, sid, **kw):
        if "especes" in kw: kw["especes"] = json.dumps(kw["especes"])
        self._w(f"UPDATE sites SET {','.join(f'{k}=?' for k in kw)} WHERE id=?",
                list(kw.values()) + [sid])

    def del_site(self, sid):
        self._w("DELETE FROM sites WHERE id=?", (sid,))

    # ── Animals ───────────────────────────────────────────────────────────────
    def add_animal(self, site_id, rfid, nom, espece, sous_cat, race, sexe, dob,
                   date_arrivee="", poids=0, enclos="", pere="", mere="",
                   gp_pm="", gp_pf="", gp_mm="", gp_mf="",
                   notes="", vaccins=None, acquisition=0):
        v = json.dumps(vaccins or [])
        with self._lk:
            self.cx.execute(
                """INSERT INTO animals(site_id,rfid,nom,espece,sous_categorie,race,sexe,dob,
                   date_arrivee,poids,enclos,pere,mere,gp_pm,gp_pf,gp_mm,gp_mf,notes,vaccins,acquisition)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (site_id, rfid, nom, espece, sous_cat, race, sexe, dob,
                 date_arrivee, poids, enclos, pere, mere, gp_pm, gp_pf, gp_mm, gp_mf, notes, v, acquisition))
            self.cx.commit()
            return self.cx.execute("SELECT last_insert_rowid()").fetchone()[0]

    @staticmethod
    def _fix_animal(d):
        """Ajoute les valeurs par défaut pour les colonnes ajoutées par migration."""
        d["vaccins"]         = json.loads(d.get("vaccins") or "[]")
        d.setdefault("statut_etat",    "stable")
        d.setdefault("sous_categorie", "")
        d.setdefault("date_arrivee",   "")
        d.setdefault("poids",          0)
        d.setdefault("actif",          1)
        return d

    def get_animals(self, site_id, espece=None):
        q = "SELECT * FROM animals WHERE site_id=?"
        a = [site_id]
        if espece: q += " AND espece=?"; a.append(espece)
        q += " ORDER BY nom"
        out = []
        for r in self._q(q, a).fetchall():
            out.append(self._fix_animal(dict(r)))
        return out

    def get_animal(self, aid=None, rfid=None):
        r = (self._q("SELECT * FROM animals WHERE id=?", (aid,)) if aid
             else self._q("SELECT * FROM animals WHERE rfid=?", (rfid,))).fetchone()
        if not r: return None
        return self._fix_animal(dict(r))

    def upd_animal(self, aid, **kw):
        if "vaccins" in kw and isinstance(kw["vaccins"], list): kw["vaccins"] = json.dumps(kw["vaccins"])
        self._w(f"UPDATE animals SET {','.join(f'{k}=?' for k in kw)} WHERE id=?",
                list(kw.values()) + [aid])

    def del_animal(self, aid):
        self._w("DELETE FROM animals WHERE id=?", (aid,))

    def search_animals(self, site_id, q="", etat=""):
        sql = "SELECT * FROM animals WHERE site_id=?"
        args = [site_id]
        if q:
            sql += " AND (rfid LIKE ? OR nom LIKE ?)"
            args += [f"%{q}%", f"%{q}%"]
        # Only filter by statut_etat if column exists
        if etat:
            try:
                sql2 = sql + " AND statut_etat=?" + " ORDER BY nom"
                rows = self._q(sql2, args + [etat]).fetchall()
                out = []
                for r in rows:
                    d = dict(r); d["vaccins"] = json.loads(d.get("vaccins") or "[]")
                    out.append(d)
                return out
            except Exception:
                pass  # column missing, fall through without filter
        sql += " ORDER BY nom"
        out = []
        for r in self._q(sql, args).fetchall():
            d = dict(r)
            d["vaccins"] = json.loads(d.get("vaccins") or "[]")
            d.setdefault("statut_etat", "stable")
            d.setdefault("sous_categorie", "")
            d.setdefault("date_arrivee", "")
            d.setdefault("poids", 0)
            out.append(d)
        return out

    # ── Enclos ────────────────────────────────────────────────────────────────
    def get_enclos(self, site_id):
        r = [x[0] for x in self._q("SELECT nom FROM enclos WHERE site_id=? ORDER BY nom", (site_id,)).fetchall()]
        if r: return r
        return [x[0] for x in self._q("SELECT DISTINCT enclos FROM animals WHERE site_id=? AND enclos!='' ORDER BY enclos", (site_id,)).fetchall()]

    def enclos_list(self, site_id):
        return [dict(r) for r in self._q("SELECT * FROM enclos WHERE site_id=? ORDER BY nom", (site_id,)).fetchall()]

    def enclos_add(self, site_id, nom):
        nom = nom.strip()
        if not nom: return None
        e = self._q("SELECT id FROM enclos WHERE site_id=? AND nom=?", (site_id, nom)).fetchone()
        if e: return e[0]
        with self._lk:
            self.cx.execute("INSERT INTO enclos(site_id,nom) VALUES(?,?)", (site_id, nom))
            self.cx.commit()
            return self.cx.execute("SELECT last_insert_rowid()").fetchone()[0]

    def enclos_ensure(self, site_id, nom):
        if nom and nom.strip(): self.enclos_add(site_id, nom.strip())

    # ── Temperatures ──────────────────────────────────────────────────────────
    def add_temp(self, rfid, site_id, tc, tf, statut):
        self._w("INSERT INTO temps(rfid,site_id,tc,tf,statut) VALUES(?,?,?,?,?)",
                (rfid, site_id, round(tc,2), round(tf,1), statut))

    def last_temp(self, rfid):
        r = self._q("SELECT * FROM temps WHERE rfid=? ORDER BY ts DESC LIMIT 1", (rfid,)).fetchone()
        return dict(r) if r else None

    def temp_history(self, rfid, hours=24):
        since = (datetime.now()-timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        return [dict(r) for r in self._q(
            "SELECT ts,tc,tf,statut FROM temps WHERE rfid=? AND ts>=? ORDER BY ts", (rfid, since)).fetchall()]

    def avgs_24h(self, site_id):
        return [dict(r) for r in self._q("""
            SELECT a.rfid,a.nom,a.espece,a.sexe,
            ROUND(AVG(t.tc),2) avg, ROUND(MIN(t.tc),2) min,
            ROUND(MAX(t.tc),2) max, COUNT(*) cnt
            FROM temps t JOIN animals a ON t.rfid=a.rfid
            WHERE t.site_id=? AND t.ts>=datetime('now','-24 hours')
            GROUP BY t.rfid ORDER BY avg DESC""", (site_id,)).fetchall()]

    def recent_readings(self, site_id, limit=20):
        return [dict(r) for r in self._q("""
            SELECT t.rfid, a.nom, t.tc, t.tf, t.statut, t.ts
            FROM temps t LEFT JOIN animals a ON t.rfid=a.rfid
            WHERE t.site_id=? ORDER BY t.ts DESC LIMIT ?""", (site_id, limit)).fetchall()]

    def current_animal_stats(self, site_id):
        stats = {"Normal":0,"Fievre":0,"Elevee":0,"Hypothermie":0,"En chaleur":0,"Sans mesure":0}
        rows = self._q("""SELECT t.statut FROM temps t
            INNER JOIN (SELECT rfid, MAX(id) AS max_id FROM temps WHERE site_id=? GROUP BY rfid) latest
            ON t.id = latest.max_id""", (site_id,)).fetchall()
        measured = len(rows)
        for r in rows: stats[r[0]] = stats.get(r[0], 0) + 1
        total = self._q("SELECT COUNT(*) FROM animals WHERE site_id=?", (site_id,)).fetchone()[0]
        stats["Sans mesure"] = max(0, total - measured)
        return stats

    # ── Traitements ───────────────────────────────────────────────────────────
    def add_traitement(self, rfid, site_id, date_t, traitement, posologie, duree, notes=""):
        self._w("INSERT INTO traitements(rfid,site_id,date_traitement,traitement,posologie,duree,notes) VALUES(?,?,?,?,?,?,?)",
                (rfid, site_id, date_t, traitement, posologie, duree, notes))
        # Mettre à jour statut bête → traitement
        self._w("UPDATE animals SET statut_etat='traitement' WHERE rfid=?", (rfid,))

    def get_traitements(self, rfid=None, site_id=None):
        if rfid:
            return [dict(r) for r in self._q("SELECT * FROM traitements WHERE rfid=? ORDER BY ts DESC", (rfid,)).fetchall()]
        return [dict(r) for r in self._q("""
            SELECT t.*, a.nom FROM traitements t LEFT JOIN animals a ON t.rfid=a.rfid
            WHERE t.site_id=? ORDER BY t.ts DESC""", (site_id,)).fetchall()]

    def del_traitement(self, tid):
        self._w("DELETE FROM traitements WHERE id=?", (tid,))

    # ── Vaccinations ──────────────────────────────────────────────────────────
    def add_vaccination(self, rfid, site_id, date_v, vaccin, posologie, duree, notes=""):
        self._w("INSERT INTO vaccinations(rfid,site_id,date_vaccin,vaccin,posologie,duree,notes) VALUES(?,?,?,?,?,?,?)",
                (rfid, site_id, date_v, vaccin, posologie, duree, notes))

    def get_vaccinations(self, rfid=None, site_id=None):
        if rfid:
            return [dict(r) for r in self._q("SELECT * FROM vaccinations WHERE rfid=? ORDER BY ts DESC", (rfid,)).fetchall()]
        return [dict(r) for r in self._q("""
            SELECT v.*, a.nom FROM vaccinations v LEFT JOIN animals a ON v.rfid=a.rfid
            WHERE v.site_id=? ORDER BY v.ts DESC""", (site_id,)).fetchall()]

    def del_vaccination(self, vid):
        self._w("DELETE FROM vaccinations WHERE id=?", (vid,))

    # ── Gestations ────────────────────────────────────────────────────────────
    def add_gestation(self, rfid, site_id, date_saillie, date_prevue, notes=""):
        self._w("INSERT INTO gestations(rfid,site_id,date_saillie,date_naissance_prevue,notes) VALUES(?,?,?,?,?)",
                (rfid, site_id, date_saillie, date_prevue, notes))

    def get_gestations(self, rfid=None, site_id=None):
        if rfid:
            return [dict(r) for r in self._q("SELECT * FROM gestations WHERE rfid=? ORDER BY ts DESC", (rfid,)).fetchall()]
        return [dict(r) for r in self._q("""
            SELECT g.*, a.nom FROM gestations g LEFT JOIN animals a ON g.rfid=a.rfid
            WHERE g.site_id=? ORDER BY g.ts DESC""", (site_id,)).fetchall()]

    def upd_gestation(self, gid, **kw):
        self._w(f"UPDATE gestations SET {','.join(f'{k}=?' for k in kw)} WHERE id=?",
                list(kw.values()) + [gid])

    # ── Alimentation ──────────────────────────────────────────────────────────
    def add_alimentation(self, rfid, site_id, date_r, aliment, quantite, unite, notes=""):
        self._w("INSERT INTO alimentation(rfid,site_id,date_repas,aliment,quantite,unite,notes) VALUES(?,?,?,?,?,?,?)",
                (rfid, site_id, date_r, aliment, quantite, unite, notes))

    def get_alimentation(self, rfid=None, site_id=None, days=7):
        since = (datetime.now()-timedelta(days=days)).strftime("%Y-%m-%d")
        if rfid:
            return [dict(r) for r in self._q("SELECT * FROM alimentation WHERE rfid=? AND date_repas>=? ORDER BY ts DESC", (rfid, since)).fetchall()]
        return [dict(r) for r in self._q("""
            SELECT al.*, a.nom FROM alimentation al LEFT JOIN animals a ON al.rfid=a.rfid
            WHERE al.site_id=? AND al.date_repas>=? ORDER BY al.ts DESC""", (site_id, since)).fetchall()]

    # ── Notifications ─────────────────────────────────────────────────────────
    def add_notif(self, uid, msg, type_="info", rfid="", site_id=0):
        self._w("INSERT INTO notifs(uid,msg,type,rfid,site_id) VALUES(?,?,?,?,?)", (uid, msg, type_, rfid, site_id))

    def get_notifs(self, uid, limit=80):
        return [dict(r) for r in self._q("SELECT * FROM notifs WHERE uid=? ORDER BY ts DESC LIMIT ?", (uid, limit)).fetchall()]

    def unread_count(self, uid):
        return self._q("SELECT COUNT(*) FROM notifs WHERE uid=? AND read=0", (uid,)).fetchone()[0]

    def mark_read(self, uid):
        self._w("UPDATE notifs SET read=1 WHERE uid=?", (uid,))

    # ── Config ────────────────────────────────────────────────────────────────
    def get_email_cfg(self, uid):
        r = self._q("SELECT * FROM email_cfg WHERE uid=?", (uid,)).fetchone()
        return dict(r) if r else {"smtp":"smtp.gmail.com","port":"587","user":"","password":"","dest":"","enabled":0}

    def save_email_cfg(self, uid, smtp, port, user, password, dest, enabled):
        if self._q("SELECT 1 FROM email_cfg WHERE uid=?", (uid,)).fetchone():
            self._w("UPDATE email_cfg SET smtp=?,port=?,user=?,password=?,dest=?,enabled=? WHERE uid=?",
                    (smtp, port, user, password, dest, enabled, uid))
        else:
            self._w("INSERT INTO email_cfg(uid,smtp,port,user,password,dest,enabled) VALUES(?,?,?,?,?,?,?)",
                    (uid, smtp, port, user, password, dest, enabled))

    def get_serial_cfg(self, uid):
        r = self._q("SELECT * FROM serial_cfg WHERE uid=?", (uid,)).fetchone()
        return dict(r) if r else {"port":"","baudrate":"9600","active":0}

    def save_serial_cfg(self, uid, port, baudrate, active=0):
        if self._q("SELECT 1 FROM serial_cfg WHERE uid=?", (uid,)).fetchone():
            self._w("UPDATE serial_cfg SET port=?,baudrate=?,active=? WHERE uid=?", (port, baudrate, active, uid))
        else:
            self._w("INSERT INTO serial_cfg(uid,port,baudrate,active) VALUES(?,?,?,?)", (uid, port, baudrate, active))

    # ── Refs (vaccins/traitements/aliments) ───────────────────────────────────
    def get_vaccins_ref(self, espece=""):
        if espece:
            r = [x[0] for x in self._q("SELECT nom FROM vaccins_ref WHERE espece=? OR espece='' ORDER BY nom", (espece,)).fetchall()]
        else:
            r = [x[0] for x in self._q("SELECT nom FROM vaccins_ref ORDER BY nom").fetchall()]
        return r or VACCINS_DB.get(espece, []) or list(set(sum(VACCINS_DB.values(), [])))

    def add_vaccin_ref(self, nom, espece=""):
        try: self._w("INSERT INTO vaccins_ref(nom,espece) VALUES(?,?)", (nom.strip(), espece))
        except: pass

    def get_traitements_ref(self):
        r = [x[0] for x in self._q("SELECT nom FROM traitements_ref ORDER BY nom").fetchall()]
        return r or TRAITEMENTS_DB

    def add_traitement_ref(self, nom):
        try: self._w("INSERT INTO traitements_ref(nom) VALUES(?)", (nom.strip(),))
        except: pass

    def get_aliments_ref(self):
        r = [x[0] for x in self._q("SELECT nom FROM aliments_ref ORDER BY nom").fetchall()]
        return r or ALIMENTS_DB

    def add_aliment_ref(self, nom):
        try: self._w("INSERT INTO aliments_ref(nom) VALUES(?)", (nom.strip(),))
        except: pass


# ══════════════════════════════════════════════════════════════════════════════
#  SERIAL MANAGER
# ══════════════════════════════════════════════════════════════════════════════
class SerialManager:
    def __init__(self):
        self._conn = None; self._thread = None; self._running = False
        self.queue = queue.Queue(); self.status = "stopped"
        self.port = ""; self.baudrate = 9600; self._lock = threading.Lock()

    def start(self, port, baudrate=9600):
        self.stop(); self.port = port; self.baudrate = int(baudrate)
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True); self._thread.start()

    def stop(self):
        self._running = False
        with self._lock: conn = self._conn; self._conn = None
        if conn:
            try: conn.close()
            except: pass
        self.status = "stopped"

    def _run(self):
        if not SERIAL_OK: self.status = "error:pyserial manquant"; return
        try:
            conn = serial.Serial(self.port, self.baudrate, timeout=1)
            with self._lock: self._conn = conn
            self.status = "running"
            while self._running:
                try:
                    raw = conn.readline().decode("utf-8", errors="ignore").strip()
                    if not self._running: break
                    if raw:
                        p = self._parse(raw)
                        if p: self.queue.put(p)
                except Exception as e:
                    if self._running: self.status = f"error:{e}"; break
        except Exception as e: self.status = f"error:{e}"
        finally:
            self._running = False
            with self._lock: self._conn = None

    @staticmethod
    def _parse(raw):
        raw = raw.strip().rstrip(";, \r\n")
        m = re.match(r"ID[:\s]*([A-Za-z0-9]+)[;:\s]+([0-9A-Fa-f]+\.?[0-9]*)F?", raw, re.IGNORECASE)
        if m:
            val = m.group(2)
            try:
                tf = float(val) if '.' in val else float(int(val,16) if len(val)==4 and all(c in '0123456789ABCDEFabcdef' for c in val) else val)
            except: tf = float(re.sub(r"[^\d.]","",val))
            return m.group(1).strip(), tf
        m = re.match(r"([A-Za-z0-9]{6,12})[:\s]+([0-9]+\.?[0-9]*)", raw)
        if m: return m.group(1).strip(), float(m.group(2))
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  WIDGET HELPERS — style Mikyas
# ══════════════════════════════════════════════════════════════════════════════
def pill_btn(parent, text, cmd, bg, fg="#FFFFFF", font=("Segoe UI",9,"bold"), padx=16, pady=5, **kw):
    """Bouton pill coloré style Mikyas"""
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, font=font,
                  relief="flat", padx=padx, pady=pady, cursor="hand2",
                  activebackground=bg, activeforeground=fg, bd=0, **kw)
    return b

def section_label(parent, text, bg):
    f = tk.Frame(parent, bg=bg); f.pack(fill="x", pady=(8,2))
    tk.Frame(f, bg=PAL["border_dark"], height=1).pack(fill="x")
    lf = tk.Frame(f, bg=bg); lf.pack(fill="x", pady=2)
    tk.Label(lf, text=text, font=("Segoe UI",8,"bold"), fg=PAL["text_sub"],
             bg=bg, padx=8).pack(side="left")
    return f

def entry_row(parent, label, var, bg, width=18, is_pwd=False):
    row = tk.Frame(parent, bg=bg); row.pack(fill="x", pady=2)
    tk.Label(row, text=label, font=("Segoe UI",8,"bold"), fg=PAL["text_sub"],
             bg=bg, width=14, anchor="w").pack(side="left", padx=(0,4))
    ef = tk.Frame(row, bg=PAL["bg_input"], highlightthickness=1,
                  highlightbackground=PAL["border"]); ef.pack(side="left", fill="x", expand=True)
    e = tk.Entry(ef, textvariable=var, font=("Segoe UI",9), bg=PAL["bg_input"],
                 fg=PAL["text"], relief="flat", insertbackground=PAL["text"],
                 show="●" if is_pwd else "")
    e.pack(fill="x", padx=6, pady=4)
    return e

def combo_row(parent, label, var, values, bg, width=16, state="readonly"):
    row = tk.Frame(parent, bg=bg); row.pack(fill="x", pady=2)
    tk.Label(row, text=label, font=("Segoe UI",8,"bold"), fg=PAL["text_sub"],
             bg=bg, width=14, anchor="w").pack(side="left", padx=(0,4))
    cb = ttk.Combobox(row, textvariable=var, values=values, width=width,
                      state=state, font=("Segoe UI",9))
    cb.pack(side="left", fill="x", expand=True)
    return cb

def status_dot(parent, etat, size=14):
    """Bouton rond coloré représentant l'état"""
    colors = {"stable": PAL["stable"], "instable": PAL["instable"], "traitement": PAL["traitement"]}
    col = colors.get(etat, PAL["btn_gray"])
    cv = tk.Canvas(parent, width=size, height=size, bg=parent.cget("bg"),
                   highlightthickness=0)
    cv.create_oval(1,1,size-1,size-1, fill=col, outline="white", width=1)
    return cv

class ScrollFrame(tk.Frame):
    def __init__(self, parent, bg, **kw):
        super().__init__(parent, bg=bg, **kw)
        self.cv = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=bg)
        self._win = self.cv.create_window((0,0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfig(self._win, width=e.width))
        self.bind("<Enter>", lambda e: self.cv.bind_all("<MouseWheel>", lambda ev: self.cv.yview_scroll(-1*(ev.delta//120),"units")))
        self.bind("<Leave>", lambda e: self.cv.unbind_all("<MouseWheel>"))

def sep(parent, bg="#D0D3D8", h=1):
    tk.Frame(parent, bg=bg, height=h).pack(fill="x")

def card(parent, bg=None, border=None, **kw):
    bg = bg or PAL["bg_card"]; border = border or PAL["border"]
    return tk.Frame(parent, bg=bg, highlightthickness=1, highlightbackground=border, **kw)


# ══════════════════════════════════════════════════════════════════════════════
#  BASE PAGE
# ══════════════════════════════════════════════════════════════════════════════
class Page(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=PAL["bg"])
        self.app = app; self.db = app.db; self.user = app.user

    @property
    def T(self): return PAL


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════
class LoginPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app); self._build()

    def _build(self):
        # Layout 2 colonnes
        left = tk.Frame(self, bg=PAL["bg_header"], width=380)
        left.pack(side="left", fill="y"); left.pack_propagate(False)

        # Panneau gauche décoratif
        tk.Frame(left, bg=PAL["bg_header"]).pack(expand=True)
        tk.Label(left, text="🐄", font=("Segoe UI",52), bg=PAL["bg_header"], fg="white").pack()
        tk.Label(left, text="BovTemp", font=("Segoe UI",26,"bold"),
                 bg=PAL["bg_header"], fg="white").pack(pady=(4,2))
        tk.Label(left, text="Plateforme de gestion d'élevage",
                 font=("Segoe UI",10), bg=PAL["bg_header"], fg="#AAAAAA").pack()
        tk.Frame(left, bg="#444444", height=1).pack(fill="x", padx=40, pady=20)
        for f in ["● Suivi du bétail en temps réel","● Traitements & vaccinations",
                  "● Suivi de grossesse","● Alimentation","● Statistiques & alertes"]:
            tk.Label(left, text=f, font=("Segoe UI",9), bg=PAL["bg_header"],
                     fg="#BBBBBB").pack(pady=3)
        tk.Frame(left, bg=PAL["bg_header"]).pack(expand=True)

        # Panneau droit
        right = tk.Frame(self, bg=PAL["bg_main"]); right.pack(side="right", fill="both", expand=True)
        tk.Frame(right, bg=PAL["bg_main"]).pack(expand=True, fill="y")
        form = tk.Frame(right, bg=PAL["bg_main"], padx=60); form.pack()

        tk.Label(form, text="Connexion", font=("Segoe UI",20,"bold"),
                 fg=PAL["text"], bg=PAL["bg_main"]).pack(anchor="w")
        tk.Label(form, text="Accédez à votre espace de gestion",
                 font=("Segoe UI",9), fg=PAL["text_sub"], bg=PAL["bg_main"]).pack(anchor="w", pady=(2,24))

        self.v_email = tk.StringVar(); self.v_pwd = tk.StringVar()
        self._err = tk.StringVar()

        for lbl, var, is_pwd in [("Email", self.v_email, False), ("Mot de passe", self.v_pwd, True)]:
            tk.Label(form, text=lbl, font=("Segoe UI",8,"bold"), fg=PAL["text_sub"],
                     bg=PAL["bg_main"]).pack(anchor="w", pady=(0,3))
            row = tk.Frame(form, bg=PAL["bg_input"], highlightthickness=1,
                           highlightbackground=PAL["border"]); row.pack(fill="x", pady=(0,12))
            e = tk.Entry(row, textvariable=var, font=("Segoe UI",10), bg=PAL["bg_input"],
                         fg=PAL["text"], relief="flat", show="●" if is_pwd else "")
            e.pack(side="left", fill="x", expand=True, padx=12, pady=9)
            e.bind("<Return>", lambda _: self._login())

        tk.Label(form, textvariable=self._err, font=("Segoe UI",8),
                 fg=PAL["btn_red"], bg=PAL["bg_main"]).pack(anchor="w", pady=(0,10))

        pill_btn(form, "  ▶  Se connecter  ", self._login,
                 bg=PAL["btn_connect"], pady=10).pack(fill="x")
        tk.Frame(form, bg=PAL["bg_main"], height=10).pack()
        sep(form, PAL["border"])
        tk.Frame(form, bg=PAL["bg_main"], height=10).pack()
        tk.Button(form, text="Créer un compte →", font=("Segoe UI",9),
                  fg=PAL["accent"], bg=PAL["bg_main"], relief="flat", cursor="hand2",
                  command=lambda: self.app.goto("register")).pack()

        tk.Frame(right, bg=PAL["bg_main"]).pack(expand=True, fill="y")

        cfg = _load_cfg()
        if cfg.get("email"): self.v_email.set(cfg["email"])

    def _login(self):
        email = self.v_email.get().strip(); pwd = self.v_pwd.get()
        if not email or not pwd: self._err.set("Champs obligatoires."); return
        user = self.db.login(email, pwd)
        if not user: self._err.set("Email ou mot de passe incorrect."); return
        self.app.user = user
        self.app.goto("accueil")


# ══════════════════════════════════════════════════════════════════════════════
#  REGISTER PAGE
# ══════════════════════════════════════════════════════════════════════════════
class RegisterPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app); self._build()

    def _build(self):
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=16, pady=10); ti.pack(fill="x")
        tk.Button(ti, text="← Retour", font=("Segoe UI",9), fg="#AAAAAA",
                  bg=PAL["bg_header"], relief="flat", cursor="hand2",
                  command=lambda: self.app.goto("login")).pack(side="left")
        tk.Label(ti, text="🐄  BovTemp — Créer un compte", font=("Segoe UI",11,"bold"),
                 fg="white", bg=PAL["bg_header"]).pack(side="left", padx=16)

        sf = ScrollFrame(self, PAL["bg"]); sf.pack(fill="both", expand=True)
        body = tk.Frame(sf.inner, bg=PAL["bg"], padx=80, pady=24); body.pack(fill="x")

        tk.Label(body, text="Informations du compte", font=("Segoe UI",14,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(0,16))

        self.v = {k: tk.StringVar() for k in ["prenom","nom","email","tel","pwd","pwd2"]}
        FIELDS = [[("Prénom *","prenom",False),("Nom *","nom",False)],
                  [("Email *","email",False),("Téléphone","tel",False)],
                  [("Mot de passe *","pwd",True),("Confirmer *","pwd2",True)]]
        for row_f in FIELDS:
            row = tk.Frame(body, bg=PAL["bg"]); row.pack(fill="x", pady=4)
            for lbl,key,is_pwd in row_f:
                col = tk.Frame(row, bg=PAL["bg"]); col.pack(side="left",fill="x",expand=True,padx=(0,12))
                tk.Label(col,text=lbl,font=("Segoe UI",8,"bold"),fg=PAL["text_sub"],bg=PAL["bg"]).pack(anchor="w",pady=(0,2))
                ef=tk.Frame(col,bg=PAL["bg_input"],highlightthickness=1,highlightbackground=PAL["border"]); ef.pack(fill="x")
                tk.Entry(ef,textvariable=self.v[key],font=("Segoe UI",9),bg=PAL["bg_input"],
                         fg=PAL["text"],relief="flat",show="●" if is_pwd else "").pack(fill="x",padx=8,pady=7)

        # Site
        tk.Label(body, text="Premier site d'élevage", font=("Segoe UI",14,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(20,12))
        self.vs = {k: tk.StringVar() for k in ["nom_site","ville","pays"]}
        self.vs["pays"].set("France")
        for lbl,key in [("Nom du site *","nom_site"),("Ville","ville"),("Pays","pays")]:
            r = tk.Frame(body, bg=PAL["bg"]); r.pack(fill="x", pady=4)
            tk.Label(r,text=lbl,font=("Segoe UI",8,"bold"),fg=PAL["text_sub"],bg=PAL["bg"],width=12,anchor="w").pack(side="left")
            ef=tk.Frame(r,bg=PAL["bg_input"],highlightthickness=1,highlightbackground=PAL["border"]); ef.pack(side="left",fill="x",expand=True)
            tk.Entry(ef,textvariable=self.vs[key],font=("Segoe UI",9),bg=PAL["bg_input"],fg=PAL["text"],relief="flat").pack(fill="x",padx=8,pady=7)

        self._err = tk.Label(body,text="",font=("Segoe UI",8),fg=PAL["btn_red"],bg=PAL["bg"])
        self._err.pack(anchor="w",pady=(10,0))
        bf = tk.Frame(body, bg=PAL["bg"]); bf.pack(fill="x", pady=12)
        pill_btn(bf,"✓  Créer mon compte",self._create,bg=PAL["btn_connect"],pady=9).pack(side="right")
        pill_btn(bf,"Annuler",lambda:self.app.goto("login"),bg=PAL["btn_gray"],pady=9).pack(side="right",padx=(0,8))

    def _create(self):
        v = {k:x.get().strip() for k,x in self.v.items()}
        if not all([v["prenom"],v["nom"],v["email"],v["pwd"]]):
            self._err.config(text="Champs obligatoires manquants."); return
        if v["pwd"] != v["pwd2"]:
            self._err.config(text="Mots de passe différents."); return
        if len(v["pwd"]) < 6:
            self._err.config(text="Mot de passe trop court."); return
        ok, msg = self.db.reg(v["nom"],v["prenom"],v["email"],v.get("tel",""),v["pwd"])
        if not ok: self._err.config(text=msg); return
        user = self.db.login(v["email"], v["pwd"])
        nom_site = self.vs["nom_site"].get().strip() or "Mon élevage"
        self.db.add_site(user["id"], nom_site, "", self.vs["ville"].get(),
                         self.vs["pays"].get(), list(ESPECE_LABEL.keys()), 0)
        self.db.add_notif(user["id"], f"Bienvenue {v['prenom']} !", "success")
        self.app.user = user; self.app.goto("accueil")


# ══════════════════════════════════════════════════════════════════════════════
#  ÉCRAN D'ACCUEIL — ImageButtons style
# ══════════════════════════════════════════════════════════════════════════════
class AccueilPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app); self._build()

    def _build(self):
        # Header bandeau sombre
        hdr = tk.Frame(self, bg=PAL["bg_header"]); hdr.pack(fill="x")
        hi  = tk.Frame(hdr, bg=PAL["bg_header"], padx=16, pady=10); hi.pack(fill="x")
        tk.Label(hi, text="🐄  BovTemp — Tableau de bord",
                 font=("Segoe UI",13,"bold"), fg="white", bg=PAL["bg_header"]).pack(side="left")
        u = self.user
        nom_u = f"{u.get('prenom','')} {u.get('nom','')}"
        tk.Label(hi, text=f"👤 {nom_u}", font=("Segoe UI",9), fg=PAL["topbar_sub"],
                 bg=PAL["bg_header"]).pack(side="right", padx=(0,12))
        pill_btn(hi, "Déconnexion", self.app._logout, bg="#555555",
                 font=("Segoe UI",8), padx=10, pady=4).pack(side="right")

        # Sélecteur de site
        sites = self.db.get_sites(u["id"])
        site_bar = tk.Frame(self, bg=PAL["bg_sect"]); site_bar.pack(fill="x")
        sb_i = tk.Frame(site_bar, bg=PAL["bg_sect"], padx=16, pady=6); sb_i.pack(fill="x")
        tk.Label(sb_i, text="Site actif :", font=("Segoe UI",8,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_sect"]).pack(side="left")
        self._v_site = tk.StringVar()
        site_names = [s["nom"] for s in sites]
        if sites: self._v_site.set(sites[0]["nom"])
        self._sites_data = {s["nom"]: s for s in sites}
        cb = ttk.Combobox(sb_i, textvariable=self._v_site, values=site_names,
                          width=24, state="readonly", font=("Segoe UI",9))
        cb.pack(side="left", padx=(8,0))
        cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_stats())
        pill_btn(sb_i, "+ Nouveau site", self._add_site, bg=PAL["btn_blue"],
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="left", padx=8)

        # Zone principale
        main = ScrollFrame(self, PAL["bg"]); main.pack(fill="both", expand=True)
        body = main.inner

        # Titre date
        date_str = datetime.now().strftime("%A %d %B %Y").capitalize()
        tk.Label(body, text=f"Bonjour, {u.get('prenom','')} 👋  —  {date_str}",
                 font=("Segoe UI",12), fg=PAL["text_sub"], bg=PAL["bg"],
                 padx=24, pady=10).pack(anchor="w")

        # Stat bar
        self._stat_frame = tk.Frame(body, bg=PAL["bg"], padx=24); self._stat_frame.pack(fill="x", pady=(0,16))
        self._refresh_stats()

        # ── IMAGE BUTTONS — 4 grandes tuiles
        tk.Label(body, text="Accès rapide", font=("Segoe UI",11,"bold"),
                 fg=PAL["text"], bg=PAL["bg"], padx=24).pack(anchor="w", pady=(0,8))

        tiles_frame = tk.Frame(body, bg=PAL["bg"], padx=24); tiles_frame.pack(fill="x", pady=(0,20))
        tiles_frame.columnconfigure(0,weight=1); tiles_frame.columnconfigure(1,weight=1)
        tiles_frame.columnconfigure(2,weight=1); tiles_frame.columnconfigure(3,weight=1)

        TILES = [
            ("🐄", "Suivi du Bétail", PAL["btn_blue"], "#1A6FA3",
             "Températures & états\nRFID temps réel",
             lambda: self.app.goto("betail")),
            ("📊", "Statistiques", PAL["btn_purple"], "#6C3483",
             "Tableaux de bord\nAnalyse des données",
             lambda: self.app.goto("stats")),
            ("🤰", "Suivi Grossesse", "#E91E63", "#AD1457",
             "Gestations en cours\nDates de mise bas",
             lambda: self.app.goto("grossesse")),
            ("🌾", "Alimentation", PAL["btn_teal"], "#148F77",
             "Rations & repas\nSuivi nutritionnel",
             lambda: self.app.goto("alimentation")),
        ]

        for i, (icon, title, bg1, bg2, desc, cmd) in enumerate(TILES):
            c = tk.Frame(tiles_frame, bg=bg1, cursor="hand2", relief="flat")
            c.grid(row=0, column=i, padx=6, pady=4, sticky="nsew", ipady=8)
            inner = tk.Frame(c, bg=bg1, padx=16, pady=20); inner.pack(fill="both", expand=True)
            tk.Label(inner, text=icon, font=("Segoe UI",32), bg=bg1, fg="white").pack()
            tk.Label(inner, text=title, font=("Segoe UI",11,"bold"), bg=bg1, fg="white").pack(pady=(8,4))
            tk.Label(inner, text=desc, font=("Segoe UI",8), bg=bg1, fg="#DDDDDD",
                     justify="center").pack()
            for w in [c, inner]:
                w.bind("<Button-1>", lambda e, fn=cmd: fn())
                w.bind("<Enter>", lambda e, f=c, b=bg2: f.config(bg=b))
                w.bind("<Leave>", lambda e, f=c, b=bg1: f.config(bg=b))

        # ── Raccourcis Traitements & Vaccins
        tk.Label(body, text="Gestion sanitaire", font=("Segoe UI",11,"bold"),
                 fg=PAL["text"], bg=PAL["bg"], padx=24).pack(anchor="w", pady=(8,8))
        quick = tk.Frame(body, bg=PAL["bg"], padx=24); quick.pack(fill="x", pady=(0,20))
        for txt, ico, col, cmd in [
            ("Traitements", "💊", PAL["btn_orange"], lambda: self.app.goto("traitements")),
            ("Vaccinations", "💉", "#9B59B6", lambda: self.app.goto("vaccins")),
            ("Back-office", "⚙", PAL["btn_gray"], lambda: self.app.goto("backoffice")),
        ]:
            f = tk.Frame(quick, bg=col, cursor="hand2"); f.pack(side="left", padx=(0,10))
            fi = tk.Frame(f, bg=col, padx=20, pady=14); fi.pack()
            tk.Label(fi, text=ico+" "+txt, font=("Segoe UI",10,"bold"), bg=col, fg="white").pack()
            for w in [f, fi]: w.bind("<Button-1>", lambda e, fn=cmd: fn())

    def _refresh_stats(self):
        for w in self._stat_frame.winfo_children(): w.destroy()
        site_nom = self._v_site.get()
        if not site_nom or site_nom not in self._sites_data: return
        site = self._sites_data[site_nom]
        sid = site["id"]
        stats = self.db.current_animal_stats(sid)
        total = self.db._q("SELECT COUNT(*) FROM animals WHERE site_id=?", (sid,)).fetchone()[0]
        try:
            instable = self.db._q("SELECT COUNT(*) FROM animals WHERE site_id=? AND statut_etat='instable'", (sid,)).fetchone()[0]
            trt      = self.db._q("SELECT COUNT(*) FROM animals WHERE site_id=? AND statut_etat='traitement'", (sid,)).fetchone()[0]
        except Exception:
            instable = 0; trt = 0

        for lbl, val, col in [
            ("Total animaux", str(total), PAL["btn_blue"]),
            ("État stable", str(total-instable-trt), PAL["btn_green"]),
            ("Instables", str(instable), PAL["btn_red"]),
            ("En traitement", str(trt), PAL["btn_orange"]),
            ("Fièvre détectée", str(stats.get("Fievre",0)), "#E74C3C"),
            ("Sans mesure", str(stats.get("Sans mesure",0)), PAL["btn_gray"]),
        ]:
            f = card(self._stat_frame, PAL["bg_card"], PAL["border"])
            f.pack(side="left", padx=(0,8), ipadx=10, ipady=6)
            tk.Label(f, text=val, font=("Segoe UI",22,"bold"), fg=col, bg=PAL["bg_card"]).pack()
            tk.Label(f, text=lbl, font=("Segoe UI",7,"bold"), fg=PAL["text_light"], bg=PAL["bg_card"]).pack()

        # Mémoriser le site courant
        self.app._current_site = self._sites_data.get(site_nom)

    def _add_site(self):
        dlg = tk.Toplevel(self.app); dlg.title("Nouveau site"); dlg.grab_set()
        dlg.configure(bg=PAL["bg"]); dlg.geometry("400x280")
        tk.Frame(dlg, bg=PAL["btn_blue"], height=4).pack(fill="x")
        tk.Label(dlg, text="Nouveau site d'élevage", font=("Segoe UI",11,"bold"),
                 fg=PAL["text"], bg=PAL["bg"], padx=20, pady=12).pack(anchor="w")
        body = tk.Frame(dlg, bg=PAL["bg"], padx=24); body.pack(fill="x")
        vs = {k: tk.StringVar() for k in ["nom","ville","pays"]}
        vs["pays"].set("France")
        for lbl,key in [("Nom *","nom"),("Ville","ville"),("Pays","pays")]:
            entry_row(body, lbl, vs[key], PAL["bg"])
        def _save():
            if not vs["nom"].get().strip(): return
            self.db.add_site(self.user["id"], vs["nom"].get(), "", vs["ville"].get(),
                             vs["pays"].get(), list(ESPECE_LABEL.keys()), 0)
            dlg.destroy(); self.app.goto("accueil")
        bf = tk.Frame(dlg, bg=PAL["bg"], padx=24, pady=12); bf.pack(fill="x")
        pill_btn(bf, "Enregistrer", _save, bg=PAL["btn_connect"], pady=8).pack(side="right")
        pill_btn(bf, "Annuler", dlg.destroy, bg=PAL["btn_gray"], pady=8).pack(side="right", padx=(0,8))


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER : récupérer le site courant
# ══════════════════════════════════════════════════════════════════════════════
def get_current_site(app):
    if hasattr(app, '_current_site') and app._current_site:
        return app._current_site
    sites = app.db.get_sites(app.user["id"])
    if sites:
        app._current_site = sites[0]
        return sites[0]
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE BETAIL — Suivi du bétail avec tableau, boutons ronds, recherche
# ══════════════════════════════════════════════════════════════════════════════
class BetailPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._site = get_current_site(app)
        self._animals = []
        self._build()

    def _build(self):
        self._mk_topbar("🐄  Suivi du Bétail")

        # Toolbar avec boutons pill
        tb = tk.Frame(self, bg=PAL["bg_sect"]); tb.pack(fill="x")
        tbi = tk.Frame(tb, bg=PAL["bg_sect"], padx=12, pady=6); tbi.pack(fill="x")

        # Recherche
        sf = tk.Frame(tbi, bg=PAL["bg_input"], highlightthickness=1,
                      highlightbackground=PAL["border"]); sf.pack(side="left")
        tk.Label(sf, text="🔍", bg=PAL["bg_input"], fg=PAL["text_sub"],
                 font=("Segoe UI",9)).pack(side="left", padx=(8,4))
        self._v_search = tk.StringVar(); self._v_search.trace_add("write", lambda *_: self._filter())
        tk.Entry(sf, textvariable=self._v_search, font=("Segoe UI",9),
                 bg=PAL["bg_input"], fg=PAL["text"], relief="flat",
                 width=22).pack(side="left", padx=(0,8), pady=5)

        # Filtre état
        tk.Label(tbi, text="État:", font=("Segoe UI",8,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_sect"]).pack(side="left", padx=(12,4))
        self._v_etat = tk.StringVar(value="Tous")
        self._v_etat.trace_add("write", lambda *_: self._filter())
        for val, lbl, col in [("Tous","Tous","#555555"),("stable","● Stable",PAL["stable"]),
                               ("instable","● Instable",PAL["instable"]),("traitement","● Traitement",PAL["traitement"])]:
            b = tk.Radiobutton(tbi, text=lbl, variable=self._v_etat, value=val,
                               font=("Segoe UI",8), fg=col, bg=PAL["bg_sect"],
                               activebackground=PAL["bg_sect"], selectcolor=PAL["bg_sect"])
            b.pack(side="left", padx=4)

        # Boutons droite
        pill_btn(tbi, "+ Ajouter un animal", self._add_animal, bg=PAL["btn_green"],
                 font=("Segoe UI",8,"bold"), padx=12, pady=3).pack(side="right")

        # Zone principale : liste boutons + tableau
        paned = tk.Frame(self, bg=PAL["bg"]); paned.pack(fill="both", expand=True)

        # Panneau gauche : boutons ronds des bêtes
        left_panel = tk.Frame(paned, bg=PAL["bg_sidebar"], width=200)
        left_panel.pack(side="left", fill="y"); left_panel.pack_propagate(False)
        tk.Label(left_panel, text="Bêtes", font=("Segoe UI",9,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_sidebar"], padx=10, pady=6).pack(anchor="w")
        sep(left_panel, PAL["border"])
        self._dot_frame = ScrollFrame(left_panel, PAL["bg_sidebar"])
        self._dot_frame.pack(fill="both", expand=True)

        # Panneau droit : tableau
        right_panel = tk.Frame(paned, bg=PAL["bg_main"]); right_panel.pack(side="right", fill="both", expand=True)
        self._table_frame = tk.Frame(right_panel, bg=PAL["bg_main"])
        self._table_frame.pack(fill="both", expand=True)

        self._load_animals()
        self._filter()

    def _mk_topbar(self, title):
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Accueil", lambda: self.app.goto("accueil"), bg="#444444",
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text=title, font=("Segoe UI",12,"bold"),
                 fg="white", bg=PAL["bg_header"]).pack(side="left", padx=12)
        # Navigation rapide
        for nm, lbl, col, dest in [("🌾 Alim.", PAL["btn_teal"], "alimentation"),
                                    ("🤰 Grossesse", "#E91E63", "grossesse"),
                                    ("💊 Traitements", PAL["btn_orange"], "traitements"),
                                    ("💉 Vaccins", "#9B59B6", "vaccins"),
                                    ("📊 Stats", PAL["btn_purple"], "stats")]:
            d = dest
            pill_btn(ti, nm, lambda x=d: self.app.goto(x), bg=col,
                     font=("Segoe UI",8), padx=10, pady=3).pack(side="right", padx=2)

    def _load_animals(self):
        if not self._site: return
        self._animals = self.db.get_animals(self._site["id"])

    def _filter(self):
        q = self._v_search.get().lower()
        etat = self._v_etat.get()
        filtered = []
        for a in self._animals:
            lt = self.db.last_temp(a["rfid"])
            a["_tc"] = lt["tc"] if lt else None
            a["_ts"] = lt["ts"] if lt else None
            if q and q not in a.get("nom","").lower() and q not in a.get("rfid","").lower(): continue
            if etat != "Tous" and a.get("statut_etat","stable") != etat: continue
            filtered.append(a)
        self._filtered = filtered
        self._rebuild_view(filtered)

    def _rebuild_view(self, animals):
        # Boutons ronds gauche
        for w in self._dot_frame.inner.winfo_children(): w.destroy()
        for a in animals:
            etat = a.get("statut_etat","stable")
            row = tk.Frame(self._dot_frame.inner, bg=PAL["bg_sidebar"],
                           cursor="hand2"); row.pack(fill="x", padx=8, pady=2)
            row.bind("<Button-1>", lambda e, aid=a["id"]: self.app.goto("detail_animal", animal_id=aid))
            cv = status_dot(row, etat, 12); cv.pack(side="left", padx=(6,6), pady=6)
            cv.bind("<Button-1>", lambda e, aid=a["id"]: self.app.goto("detail_animal", animal_id=aid))
            tk.Label(row, text=a.get("nom","—")[:16], font=("Segoe UI",8),
                     fg=PAL["text"], bg=PAL["bg_sidebar"],
                     cursor="hand2").pack(side="left")
            row.bind("<Enter>", lambda e, r=row: r.config(bg=PAL["bg"]))
            row.bind("<Leave>", lambda e, r=row: r.config(bg=PAL["bg_sidebar"]))

        # Tableau droit
        for w in self._table_frame.winfo_children(): w.destroy()
        outer = tk.Frame(self._table_frame, bg=PAL["bg_main"]); outer.pack(fill="both", expand=True, padx=8, pady=6)

        cols = ("etat","rfid","nom","espece","sous_cat","tc","date_last","statut_temp")
        hdrs = {"etat":"●","rfid":"N° Tag RFID","nom":"Nom","espece":"Espèce",
                "sous_cat":"Catégorie","tc":"Temp °C","date_last":"Dernière mesure","statut_temp":"État temp."}
        widths = {"etat":30,"rfid":120,"nom":120,"espece":70,"sous_cat":110,"tc":70,"date_last":130,"statut_temp":100}

        tree = ttk.Treeview(outer, columns=cols, show="headings", height=28)
        for c in cols:
            tree.heading(c, text=hdrs[c])
            tree.column(c, width=widths.get(c,90), anchor="center" if c in ("etat","tc","statut_temp") else "w")

        colors = {"stable":PAL["stable"],"instable":PAL["instable"],"traitement":PAL["traitement"]}
        for k, col in colors.items(): tree.tag_configure(k, foreground=col)
        tree.tag_configure("fievre", foreground=PAL["btn_red"], background="#FFF0F0")
        tree.tag_configure("hypo",   foreground=PAL["btn_blue"], background="#F0F5FF")

        for a in animals:
            etat = a.get("statut_etat","stable")
            tc = a.get("_tc"); ts = a.get("_ts","")
            statut_t = get_status(tc, a.get("sexe","F")) if tc is not None else "—"
            tag = "fievre" if statut_t=="Fievre" else ("hypo" if statut_t=="Hypothermie" else etat)
            dot = {"stable":"●","instable":"●","traitement":"●"}.get(etat,"○")
            tree.insert("","end", iid=str(a["id"]), tags=(tag,),
                values=(dot, a.get("rfid",""), a.get("nom","—"),
                        ESPECE_LABEL.get(a.get("espece",""),"—"),
                        a.get("sous_categorie","—"),
                        f"{tc:.1f}" if tc else "—",
                        (ts or "")[:16] if ts else "—",
                        statut_t))

        vsb = ttk.Scrollbar(outer, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); tree.pack(fill="both", expand=True)
        tree.bind("<Double-Button-1>", lambda e: self._open_from_tree(tree))

        # Breadcrumb
        bc = tk.Label(self._table_frame, text=f"→  Accueil  /  Suivi du Bétail  ({len(animals)} animaux)",
                      font=("Segoe UI",8), fg=PAL["text_sub"], bg=PAL["bg_main"], padx=8, pady=4)
        bc.pack(anchor="w")

    def _open_from_tree(self, tree):
        sel = tree.selection()
        if sel: self.app.goto("detail_animal", animal_id=int(sel[0]))

    def _add_animal(self):
        if not self._site:
            messagebox.showwarning("", "Aucun site sélectionné."); return
        self.app.goto("edit_animal", animal_id=None, site_id=self._site["id"])


# ══════════════════════════════════════════════════════════════════════════════
#  DÉTAIL ANIMAL
# ══════════════════════════════════════════════════════════════════════════════
class DetailAnimalPage(Page):
    def __init__(self, parent, app, animal_id):
        super().__init__(parent, app)
        self.animal = self.db.get_animal(aid=animal_id)
        self.site = self.db.get_site(self.animal["site_id"]) if self.animal else None
        self._build()
        app.register_live_callback(self._on_live)

    def destroy(self):
        self.app.unregister_live_callback(self._on_live)
        super().destroy()

    def _build(self):
        a = self.animal
        if not a:
            tk.Label(self, text="Animal introuvable.", fg=PAL["text"], bg=PAL["bg"],
                     font=("Segoe UI",12)).pack(expand=True); return

        lt = self.db.last_temp(a["rfid"])
        tc = lt["tc"] if lt else None
        statut_t = get_status(tc, a.get("sexe","F"))

        # Topbar
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Bétail", lambda: self.app.goto("betail"), bg="#444444",
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text=f"  {ESPECE_ICON.get(a.get('espece','bovin'),'🐄')}  {a.get('nom','—')}",
                 font=("Segoe UI",12,"bold"), fg="white", bg=PAL["bg_header"]).pack(side="left", padx=8)
        pill_btn(ti, "✏ Modifier", lambda: self.app.goto("edit_animal", animal_id=a["id"], site_id=a["site_id"]),
                 bg=PAL["btn_blue"], font=("Segoe UI",8), padx=10, pady=3).pack(side="right")
        # Breadcrumb
        bc_txt = f"→  Accueil  /  Bétail  /  {a.get('nom','—')}"
        tk.Label(top, text=bc_txt, font=("Segoe UI",7), fg="#888888",
                 bg=PAL["bg_header"], padx=16).pack(anchor="w", pady=(0,4))

        # Hero card
        etat = a.get("statut_etat","stable")
        etat_colors = {"stable": PAL["stable"], "instable": PAL["instable"], "traitement": PAL["traitement"]}
        etat_col = etat_colors.get(etat, "#888888")

        hero = tk.Frame(self, bg=PAL["bg_main"], highlightthickness=2,
                        highlightbackground=etat_col); hero.pack(fill="x", padx=16, pady=10)
        hi = tk.Frame(hero, bg=PAL["bg_main"], padx=16, pady=12); hi.pack(fill="x")

        # Info principale
        hl = tk.Frame(hi, bg=PAL["bg_main"]); hl.pack(side="left", fill="x", expand=True)
        tk.Label(hl, text=f"{ESPECE_ICON.get(a.get('espece'),'🐄')}  {a.get('nom','—')}",
                 font=("Segoe UI",18,"bold"), fg=PAL["text"], bg=PAL["bg_main"]).pack(anchor="w")
        tk.Label(hl, text=f"Tag : {a.get('rfid','—')}  ·  {ESPECE_LABEL.get(a.get('espece',''),'—')} — {a.get('sous_categorie','—')}  ·  {a.get('race','—')}",
                 font=("Segoe UI",9), fg=PAL["text_sub"], bg=PAL["bg_main"]).pack(anchor="w", pady=(4,8))
        info_row = tk.Frame(hl, bg=PAL["bg_main"]); info_row.pack(anchor="w")
        for lbl, val in [("Naissance", a.get("dob","—")), ("Arrivée", a.get("date_arrivee","—")),
                         ("Poids", f"{a.get('poids',0)} kg"), ("Enclos", a.get("enclos","—"))]:
            f = tk.Frame(info_row, bg=PAL["bg_main"]); f.pack(side="left", padx=(0,24))
            tk.Label(f, text=lbl, font=("Segoe UI",7,"bold"), fg=PAL["text_light"], bg=PAL["bg_main"]).pack(anchor="w")
            tk.Label(f, text=val or "—", font=("Segoe UI",9), fg=PAL["text"], bg=PAL["bg_main"]).pack(anchor="w")

        # Température + état
        hr2 = tk.Frame(hi, bg=PAL["bg_main"]); hr2.pack(side="right", padx=(20,0))
        temp_col = {"Fievre": PAL["btn_red"], "Hypothermie": PAL["btn_blue"],
                    "Elevee": PAL["btn_orange"], "En chaleur": "#E91E63",
                    "Normal": PAL["stable"]}.get(statut_t, PAL["text_sub"])
        self._hero_tc = tk.Label(hr2, text=f"{tc:.1f}°C" if tc else "—",
                                  font=("Segoe UI",28,"bold"), fg=temp_col, bg=PAL["bg_main"])
        self._hero_tc.pack()
        etat_lbl = {"stable":"● Stable","instable":"● Instable","traitement":"● En traitement"}.get(etat,"—")
        self._hero_badge = tk.Label(hr2, text=etat_lbl, font=("Segoe UI",9,"bold"),
                                     fg=etat_col, bg=PAL["bg_main"])
        self._hero_badge.pack()

        # Tabs
        tab_bar = tk.Frame(self, bg=PAL["bg_sect"]); tab_bar.pack(fill="x")
        self._tabs = {}
        for tn, tl in [("info","📋 Infos"),("traitements","💊 Traitements"),
                       ("vaccins","💉 Vaccins"),("gestation","🤰 Grossesse"),
                       ("alim","🌾 Alimentation"),("historique","📈 Historique")]:
            b = tk.Button(tab_bar, text=tl, font=("Segoe UI",8,"bold"),
                          fg=PAL["text_sub"], bg=PAL["bg_sect"], relief="flat",
                          padx=14, pady=7, cursor="hand2",
                          command=lambda t=tn: self._show_tab(t))
            b.pack(side="left"); self._tabs[tn] = b

        self._tcontent = tk.Frame(self, bg=PAL["bg"]); self._tcontent.pack(fill="both", expand=True)
        self._show_tab("info")

    def _show_tab(self, tab):
        for t, b in self._tabs.items():
            b.config(bg=PAL["btn_blue"] if t==tab else PAL["bg_sect"],
                     fg="white" if t==tab else PAL["text_sub"])
        for w in self._tcontent.winfo_children(): w.destroy()
        {"info": self._t_info, "traitements": self._t_traitements,
         "vaccins": self._t_vaccins, "gestation": self._t_gestation,
         "alim": self._t_alim, "historique": self._t_hist}[tab]()

    def _t_info(self):
        a = self.animal
        sf = ScrollFrame(self._tcontent, PAL["bg"]); sf.pack(fill="both", expand=True)
        body = tk.Frame(sf.inner, bg=PAL["bg"], padx=24, pady=16); body.pack(fill="x")

        def sect(title, data):
            tk.Label(body, text=title, font=("Segoe UI",10,"bold"), fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(12,4))
            c = card(body); c.pack(fill="x")
            ci = tk.Frame(c, bg=PAL["bg_card"], padx=12, pady=10); ci.pack(fill="x")
            g = tk.Frame(ci, bg=PAL["bg_card"]); g.pack(fill="x")
            for i, (lbl, val) in enumerate(data):
                r, col = divmod(i, 3)
                f = tk.Frame(g, bg=PAL["bg_card"]); f.grid(row=r, column=col, sticky="w", padx=(0,30), pady=3)
                tk.Label(f, text=lbl, font=("Segoe UI",7,"bold"), fg=PAL["text_light"], bg=PAL["bg_card"]).pack(anchor="w")
                tk.Label(f, text=str(val) or "—", font=("Segoe UI",9), fg=PAL["text"], bg=PAL["bg_card"]).pack(anchor="w")

        sect("Identification", [
            ("Nom", a.get("nom")), ("Tag RFID", a.get("rfid")),
            ("Espèce", ESPECE_LABEL.get(a.get("espece",""),"—")),
            ("Catégorie", a.get("sous_categorie","—")), ("Race", a.get("race","—")),
            ("Sexe", "Femelle" if a.get("sexe","F")=="F" else "Mâle"),
        ])
        sect("Données physiques", [
            ("Date naissance", a.get("dob","—")), ("Date arrivée", a.get("date_arrivee","—")),
            ("Poids", f"{a.get('poids',0)} kg"), ("Enclos", a.get("enclos","—")),
            ("Site", self.site.get("nom","—") if self.site else "—"),
        ])
        if a.get("notes"):
            tk.Label(body, text="Notes", font=("Segoe UI",10,"bold"), fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(12,4))
            c = card(body); c.pack(fill="x")
            tk.Label(c, text=a["notes"], font=("Segoe UI",9), fg=PAL["text_sub"],
                     bg=PAL["bg_card"], padx=12, pady=10, wraplength=600, justify="left").pack(anchor="w")

    def _t_traitements(self):
        a = self.animal
        body = tk.Frame(self._tcontent, bg=PAL["bg"]); body.pack(fill="both", expand=True)
        hdr = tk.Frame(body, bg=PAL["bg_sect"], padx=16, pady=8); hdr.pack(fill="x")
        tk.Label(hdr, text="💊 Historique des traitements",
                 font=("Segoe UI",10,"bold"), fg=PAL["text"], bg=PAL["bg_sect"]).pack(side="left")
        pill_btn(hdr, "+ Nouveau traitement",
                 lambda: self.app.goto("detail_traitement", rfid=a["rfid"], site_id=a["site_id"]),
                 bg=PAL["btn_orange"], font=("Segoe UI",8), padx=10, pady=3).pack(side="right")
        sep(body, PAL["border"])

        rows = self.db.get_traitements(rfid=a["rfid"])
        sf = ScrollFrame(body, PAL["bg"]); sf.pack(fill="both", expand=True)
        if not rows:
            tk.Label(sf.inner, text="Aucun traitement enregistré.",
                     font=("Segoe UI",9), fg=PAL["text_light"], bg=PAL["bg"], padx=16, pady=20).pack()
            return
        # En-tête
        hdrc = tk.Frame(sf.inner, bg=PAL["bg_sect"]); hdrc.pack(fill="x")
        for txt, w in [("Date",100),("Traitement",180),("Posologie",130),("Durée",100),("",40)]:
            tk.Label(hdrc, text=txt, font=("Segoe UI",7,"bold"), fg=PAL["text_sub"],
                     bg=PAL["bg_sect"], width=w//7, anchor="w", padx=8, pady=4).pack(side="left")
        for r in rows:
            row = tk.Frame(sf.inner, bg=PAL["bg_main"]); row.pack(fill="x")
            ri  = tk.Frame(row, bg=PAL["bg_main"], padx=8, pady=6); ri.pack(fill="x")
            for txt in [r.get("date_traitement","—"), r.get("traitement","—"),
                        r.get("posologie","—"), r.get("duree","—")]:
                tk.Label(ri, text=txt, font=("Segoe UI",8), fg=PAL["text"],
                         bg=PAL["bg_main"], width=14, anchor="w").pack(side="left", padx=(0,8))
            pill_btn(ri, "🗑", lambda rid=r["id"]: self._del_trt(rid),
                     bg=PAL["btn_red"], font=("Segoe UI",8), padx=6, pady=2).pack(side="right")
            sep(sf.inner, PAL["border"])

    def _del_trt(self, rid):
        if messagebox.askyesno("Supprimer","Supprimer ce traitement ?"): 
            self.db.del_traitement(rid); self._show_tab("traitements")

    def _t_vaccins(self):
        a = self.animal
        body = tk.Frame(self._tcontent, bg=PAL["bg"]); body.pack(fill="both", expand=True)
        hdr = tk.Frame(body, bg=PAL["bg_sect"], padx=16, pady=8); hdr.pack(fill="x")
        tk.Label(hdr, text="💉 Historique des vaccins",
                 font=("Segoe UI",10,"bold"), fg=PAL["text"], bg=PAL["bg_sect"]).pack(side="left")
        pill_btn(hdr, "+ Nouveau vaccin",
                 lambda: self.app.goto("detail_vaccin", rfid=a["rfid"], site_id=a["site_id"]),
                 bg="#9B59B6", font=("Segoe UI",8), padx=10, pady=3).pack(side="right")
        sep(body, PAL["border"])

        rows = self.db.get_vaccinations(rfid=a["rfid"])
        sf = ScrollFrame(body, PAL["bg"]); sf.pack(fill="both", expand=True)
        if not rows:
            tk.Label(sf.inner, text="Aucun vaccin enregistré.",
                     font=("Segoe UI",9), fg=PAL["text_light"], bg=PAL["bg"], padx=16, pady=20).pack(); return
        hdrc = tk.Frame(sf.inner, bg=PAL["bg_sect"]); hdrc.pack(fill="x")
        for txt, w in [("Date",100),("Vaccin",180),("Posologie",130),("Durée",100),("",40)]:
            tk.Label(hdrc, text=txt, font=("Segoe UI",7,"bold"), fg=PAL["text_sub"],
                     bg=PAL["bg_sect"], width=w//7, anchor="w", padx=8, pady=4).pack(side="left")
        for r in rows:
            row = tk.Frame(sf.inner, bg=PAL["bg_main"]); row.pack(fill="x")
            ri  = tk.Frame(row, bg=PAL["bg_main"], padx=8, pady=6); ri.pack(fill="x")
            for txt in [r.get("date_vaccin","—"), r.get("vaccin","—"),
                        r.get("posologie","—"), r.get("duree","—")]:
                tk.Label(ri, text=txt, font=("Segoe UI",8), fg=PAL["text"],
                         bg=PAL["bg_main"], width=14, anchor="w").pack(side="left", padx=(0,8))
            pill_btn(ri, "🗑", lambda vid=r["id"]: self._del_vac(vid),
                     bg=PAL["btn_red"], font=("Segoe UI",8), padx=6, pady=2).pack(side="right")
            sep(sf.inner, PAL["border"])

    def _del_vac(self, vid):
        if messagebox.askyesno("Supprimer","Supprimer ce vaccin ?"):
            self.db.del_vaccination(vid); self._show_tab("vaccins")

    def _t_gestation(self):
        a = self.animal
        body = tk.Frame(self._tcontent, bg=PAL["bg"]); body.pack(fill="both", expand=True)
        hdr = tk.Frame(body, bg=PAL["bg_sect"], padx=16, pady=8); hdr.pack(fill="x")
        tk.Label(hdr, text="🤰 Suivi de grossesse",
                 font=("Segoe UI",10,"bold"), fg=PAL["text"], bg=PAL["bg_sect"]).pack(side="left")
        if a.get("sexe","F") == "F":
            pill_btn(hdr, "+ Nouvelle gestation",
                     lambda: self._add_gestation(), bg="#E91E63",
                     font=("Segoe UI",8), padx=10, pady=3).pack(side="right")
        sep(body, PAL["border"])
        rows = self.db.get_gestations(rfid=a["rfid"])
        sf = ScrollFrame(body, PAL["bg"]); sf.pack(fill="both", expand=True)
        if not rows:
            tk.Label(sf.inner, text="Aucune gestation enregistrée.",
                     font=("Segoe UI",9), fg=PAL["text_light"], bg=PAL["bg"], padx=16, pady=20).pack(); return
        for r in rows:
            c = card(sf.inner); c.pack(fill="x", padx=12, pady=4)
            ci = tk.Frame(c, bg=PAL["bg_card"], padx=12, pady=10); ci.pack(fill="x")
            statut_g = r.get("statut","en_cours")
            col_g = PAL["stable"] if statut_g == "terminee" else "#E91E63"
            tag_g = "✓ Terminée" if statut_g == "terminee" else "⏳ En cours"
            tk.Label(ci, text=tag_g, font=("Segoe UI",8,"bold"), fg=col_g, bg=PAL["bg_card"]).pack(anchor="e")
            for lbl, val in [("Saillie", r.get("date_saillie","—")),
                             ("Naissance prévue", r.get("date_naissance_prevue","—")),
                             ("Naissance réelle", r.get("date_naissance_reelle","—") or "—"),
                             ("Petits", str(r.get("nb_petits",1))),
                             ("Poids naissance", f"{r.get('poids_naissance',0)} kg"),
                             ("Notes", r.get("notes",""))]:
                row = tk.Frame(ci, bg=PAL["bg_card"]); row.pack(anchor="w")
                tk.Label(row, text=f"{lbl} :", font=("Segoe UI",8,"bold"),
                         fg=PAL["text_sub"], bg=PAL["bg_card"], width=14, anchor="w").pack(side="left")
                tk.Label(row, text=val or "—", font=("Segoe UI",8),
                         fg=PAL["text"], bg=PAL["bg_card"]).pack(side="left")

    def _add_gestation(self):
        a = self.animal
        dlg = tk.Toplevel(self.app); dlg.title("Nouvelle gestation"); dlg.grab_set()
        dlg.configure(bg=PAL["bg"]); dlg.geometry("400x300")
        tk.Frame(dlg, bg="#E91E63", height=4).pack(fill="x")
        tk.Label(dlg, text="🤰  Nouvelle gestation", font=("Segoe UI",11,"bold"),
                 fg=PAL["text"], bg=PAL["bg"], padx=20, pady=12).pack(anchor="w")
        body = tk.Frame(dlg, bg=PAL["bg"], padx=24); body.pack(fill="x")
        v_saillie = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        v_prevue  = tk.StringVar()
        v_notes   = tk.StringVar()
        entry_row(body, "Date saillie *", v_saillie, PAL["bg"])
        entry_row(body, "Naissance prévue", v_prevue, PAL["bg"])
        entry_row(body, "Notes", v_notes, PAL["bg"])
        tk.Label(body, text="💡 Format date : JJ/MM/AAAA",
                 font=("Segoe UI",7), fg=PAL["text_light"], bg=PAL["bg"]).pack(anchor="w", pady=(4,0))
        def _save():
            self.db.add_gestation(a["rfid"], a["site_id"], v_saillie.get(), v_prevue.get(), v_notes.get())
            dlg.destroy(); self._show_tab("gestation")
        bf = tk.Frame(dlg, bg=PAL["bg"], padx=24, pady=12); bf.pack(fill="x")
        pill_btn(bf,"Valider",_save,bg=PAL["btn_connect"],pady=8).pack(side="right")
        pill_btn(bf,"Annuler",dlg.destroy,bg=PAL["btn_gray"],pady=8).pack(side="right",padx=(0,8))

    def _t_alim(self):
        a = self.animal
        body = tk.Frame(self._tcontent, bg=PAL["bg"]); body.pack(fill="both", expand=True)
        hdr = tk.Frame(body, bg=PAL["bg_sect"], padx=16, pady=8); hdr.pack(fill="x")
        tk.Label(hdr, text="🌾 Suivi de l'alimentation",
                 font=("Segoe UI",10,"bold"), fg=PAL["text"], bg=PAL["bg_sect"]).pack(side="left")
        pill_btn(hdr, "+ Ajouter repas",
                 lambda: self.app.goto("detail_alim", rfid=a["rfid"], site_id=a["site_id"]),
                 bg=PAL["btn_teal"], font=("Segoe UI",8), padx=10, pady=3).pack(side="right")
        sep(body, PAL["border"])
        rows = self.db.get_alimentation(rfid=a["rfid"], days=30)
        sf = ScrollFrame(body, PAL["bg"]); sf.pack(fill="both", expand=True)
        if not rows:
            tk.Label(sf.inner, text="Aucun repas enregistré (30 derniers jours).",
                     font=("Segoe UI",9), fg=PAL["text_light"], bg=PAL["bg"], padx=16, pady=20).pack(); return
        hdrc = tk.Frame(sf.inner, bg=PAL["bg_sect"]); hdrc.pack(fill="x")
        for txt in ["Date","Aliment","Quantité","Unité"]:
            tk.Label(hdrc, text=txt, font=("Segoe UI",7,"bold"), fg=PAL["text_sub"],
                     bg=PAL["bg_sect"], width=12, anchor="w", padx=8, pady=4).pack(side="left")
        for r in rows:
            row = tk.Frame(sf.inner, bg=PAL["bg_main"]); row.pack(fill="x")
            ri  = tk.Frame(row, bg=PAL["bg_main"], padx=8, pady=5); ri.pack(fill="x")
            for txt in [r.get("date_repas","—"), r.get("aliment","—"),
                        str(r.get("quantite",0)), r.get("unite","—")]:
                tk.Label(ri, text=txt, font=("Segoe UI",8), fg=PAL["text"],
                         bg=PAL["bg_main"], width=12, anchor="w").pack(side="left", padx=(0,8))
            sep(sf.inner, PAL["border"])

    def _t_hist(self):
        a = self.animal
        body = tk.Frame(self._tcontent, bg=PAL["bg"]); body.pack(fill="both", expand=True)
        ctrl = tk.Frame(body, bg=PAL["bg_sect"], padx=16, pady=8); ctrl.pack(fill="x")
        tk.Label(ctrl, text="📈 Historique températures",
                 font=("Segoe UI",10,"bold"), fg=PAL["text"], bg=PAL["bg_sect"]).pack(side="left")
        self._h_hours = tk.StringVar(value="24")
        for h, l in [("6","6h"),("24","24h"),("48","48h"),("168","7j")]:
            tk.Radiobutton(ctrl, text=l, variable=self._h_hours, value=h,
                           font=("Segoe UI",8), fg=PAL["btn_blue"], bg=PAL["bg_sect"],
                           activebackground=PAL["bg_sect"], selectcolor=PAL["bg_sect"],
                           command=lambda: self._draw_hist(a)).pack(side="right", padx=4)
        self._hist_f = tk.Frame(body, bg=PAL["bg_main"]); self._hist_f.pack(fill="both", expand=True)
        self._draw_hist(a)

    def _draw_hist(self, a):
        for w in self._hist_f.winfo_children(): w.destroy()
        rows = self.db.temp_history(a["rfid"], hours=int(self._h_hours.get()))
        if not MPLOT:
            tk.Label(self._hist_f, text="Installez matplotlib : pip install matplotlib",
                     fg=PAL["text_sub"], bg=PAL["bg_main"], font=("Segoe UI",9)).pack(expand=True); return
        if not rows:
            tk.Label(self._hist_f, text="Aucun historique disponible.",
                     fg=PAL["text_light"], bg=PAL["bg_main"], font=("Segoe UI",9)).pack(expand=True); return
        dates = [datetime.strptime(r["ts"],"%Y-%m-%d %H:%M:%S") for r in rows]
        temps = [r["tc"] for r in rows]
        fig = Figure(figsize=(8,3.4), dpi=96, facecolor=PAL["bg_main"])
        ax  = fig.add_subplot(111, facecolor=PAL["bg_sect"])
        fig.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.20)
        color_map = {"Normal":PAL["stable"],"Fievre":PAL["btn_red"],"Elevee":PAL["btn_orange"],
                     "Hypothermie":PAL["btn_blue"],"En chaleur":"#E91E63"}
        for i in range(len(dates)-1):
            c = color_map.get(get_status(temps[i], a.get("sexe","F")), PAL["stable"])
            ax.plot(dates[i:i+2], temps[i:i+2], color=c, lw=2.5, solid_capstyle="round")
        ax.scatter(dates, temps, c=[color_map.get(get_status(t,a.get("sexe","F")),PAL["stable"]) for t in temps],
                   s=24, zorder=5, edgecolors="white", lw=0.8)
        ax.axhline(TEMP_HIGH, lw=1, ls="--", color=PAL["btn_red"], alpha=0.5)
        ax.axhline(TEMP_LOW,  lw=1, ls="--", color=PAL["btn_blue"], alpha=0.5)
        if temps:
            avg = sum(temps)/len(temps)
            ax.axhline(avg, lw=1, ls=":", color=PAL["text_sub"], alpha=0.7)
            ax.text(dates[-1], avg+0.05, f"moy {avg:.1f}°C", fontsize=7, color=PAL["text_sub"], ha="right")
        fmt = "%d/%m %H:%M" if int(self._h_hours.get())>24 else "%H:%M"
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        fig.autofmt_xdate(rotation=30, ha="right")
        ax.set_ylabel("°C", color=PAL["text_sub"], fontsize=9)
        ax.tick_params(colors=PAL["text_sub"], labelsize=8)
        for sp in ax.spines.values(): sp.set_color(PAL["border"])
        ax.grid(True, alpha=0.3, color=PAL["border"])
        if temps:
            m = max(0.3,(max(temps)-min(temps))*0.25)
            ax.set_ylim(min(temps)-m, max(temps)+m)
        cvs = FigureCanvasTkAgg(fig, master=self._hist_f)
        cvs.draw(); cvs.get_tk_widget().pack(fill="both", expand=True)

    def _on_live(self, rfid, tc, tf, statut, info):
        if rfid != self.animal.get("rfid"): return
        color_map = {"Normal":PAL["stable"],"Fievre":PAL["btn_red"],"Elevee":PAL["btn_orange"],
                     "Hypothermie":PAL["btn_blue"],"En chaleur":"#E91E63"}
        col = color_map.get(statut, PAL["text_sub"])
        if self._hero_tc.winfo_exists(): self._hero_tc.config(text=f"{tc:.1f}°C", fg=col)


# ══════════════════════════════════════════════════════════════════════════════
#  EDIT ANIMAL
# ══════════════════════════════════════════════════════════════════════════════
class EditAnimalPage(Page):
    def __init__(self, parent, app, animal_id, site_id):
        super().__init__(parent, app)
        self.animal_id = animal_id; self.site_id = site_id
        self.animal = self.db.get_animal(aid=animal_id) if animal_id else None
        self._build()

    def _build(self):
        a = self.animal or {}; is_new = not a
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        back = (lambda: self.app.goto("detail_animal", animal_id=self.animal_id)) if not is_new else (lambda: self.app.goto("betail"))
        pill_btn(ti, "← Annuler", back, bg="#444444", font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text=f"  {'Nouvel animal' if is_new else 'Modifier — '+a.get('nom','—')}",
                 font=("Segoe UI",12,"bold"), fg="white", bg=PAL["bg_header"]).pack(side="left", padx=8)

        sf = ScrollFrame(self, PAL["bg"]); sf.pack(fill="both", expand=True)
        body = tk.Frame(sf.inner, bg=PAL["bg"], padx=48, pady=20); body.pack(fill="x")

        espece_init = a.get("espece","bovin")
        self.v = {k: tk.StringVar(value=str(a.get(k,"") or "")) for k in
                  ["rfid","nom","espece","sous_categorie","race","sexe","dob",
                   "date_arrivee","poids","enclos","pere","mere","notes"]}
        self.v["espece"].set(espece_init)
        self.v["sexe"].set(a.get("sexe","F"))
        self.v_acq = tk.BooleanVar(value=bool(a.get("acquisition",0)))

        def sec(title):
            tk.Label(body, text=title, font=("Segoe UI",11,"bold"),
                     fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(16,4))
            tk.Frame(body, bg=PAL["border_dark"], height=1).pack(fill="x")
            tk.Frame(body, bg=PAL["bg"], height=6).pack()

        def frow(*fields):
            row = tk.Frame(body, bg=PAL["bg"]); row.pack(fill="x", pady=4)
            for lbl, key, w, extra in fields:
                col = tk.Frame(row, bg=PAL["bg"]); col.pack(side="left",fill="x",expand=True,padx=(0,12))
                tk.Label(col, text=lbl, font=("Segoe UI",8,"bold"), fg=PAL["text_sub"], bg=PAL["bg"]).pack(anchor="w",pady=(0,2))
                if "values" in extra:
                    cb = ttk.Combobox(col, textvariable=self.v[key], values=extra["values"],
                                      width=w, state=extra.get("state","readonly"), font=("Segoe UI",9))
                    cb.pack(fill="x")
                    if "cmd" in extra: cb.bind("<<ComboboxSelected>>", extra["cmd"])
                else:
                    ef = tk.Frame(col, bg=PAL["bg_input"], highlightthickness=1, highlightbackground=PAL["border"]); ef.pack(fill="x")
                    tk.Entry(ef, textvariable=self.v[key], font=("Segoe UI",9), bg=PAL["bg_input"],
                             fg=PAL["text"], relief="flat").pack(fill="x", padx=8, pady=7)

        sec("Identification")
        frow(("Tag RFID *","rfid",20,{}), ("Nom *","nom",20,{}))

        # Espèce avec mise à jour sous-catégorie
        def _upd_sous(*_):
            esp = self.v["espece"].get()
            self._sous_cb["values"] = SOUS_CATEGORIES.get(esp, [])
            if not self.v["sous_categorie"].get():
                sc = SOUS_CATEGORIES.get(esp, [])
                if sc: self.v["sous_categorie"].set(sc[0])

        frow(("Espèce *","espece",14,{"values":list(ESPECE_LABEL.keys()),"cmd":_upd_sous}),
             ("Race","race",14,{}))

        # Sous-catégorie
        sc_row = tk.Frame(body, bg=PAL["bg"]); sc_row.pack(fill="x", pady=4)
        col_sc = tk.Frame(sc_row, bg=PAL["bg"]); col_sc.pack(side="left",fill="x",expand=True,padx=(0,12))
        tk.Label(col_sc, text="Sous-catégorie *", font=("Segoe UI",8,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg"]).pack(anchor="w", pady=(0,2))
        init_sous = SOUS_CATEGORIES.get(espece_init, [])
        self._sous_cb = ttk.Combobox(col_sc, textvariable=self.v["sous_categorie"],
                                      values=init_sous, width=18, state="readonly", font=("Segoe UI",9))
        if not self.v["sous_categorie"].get() and init_sous: self.v["sous_categorie"].set(init_sous[0])
        self._sous_cb.pack(fill="x")

        enclos_vals = self.db.get_enclos(self.site_id)
        frow(("Sexe","sexe",8,{"values":["F","M"]}),
             ("Date naissance","dob",14,{}),
             ("Date arrivée","date_arrivee",14,{}))
        frow(("Poids (kg)","poids",10,{}),
             ("Enclos","enclos",14,{"values":enclos_vals,"state":"normal"}))

        sec("Pedigree")
        frow(("Tag Père","pere",22,{}), ("Tag Mère","mere",22,{}))

        sec("Acquisition RFID")
        acq_row = tk.Frame(body, bg=PAL["bg"]); acq_row.pack(fill="x", pady=4)
        tk.Checkbutton(acq_row, text="Activer la collecte RFID pour cet animal",
                       variable=self.v_acq, font=("Segoe UI",9), fg=PAL["text"],
                       bg=PAL["bg"], activebackground=PAL["bg"],
                       selectcolor=PAL["bg_input"]).pack(side="left")

        sec("Notes")
        nf = tk.Frame(body, bg=PAL["bg_input"], highlightthickness=1,
                      highlightbackground=PAL["border"]); nf.pack(fill="x")
        self._notes_txt = tk.Text(nf, font=("Segoe UI",9), bg=PAL["bg_input"],
                                   fg=PAL["text"], relief="flat", height=3, wrap="word")
        self._notes_txt.pack(fill="x", padx=8, pady=6)
        if a.get("notes"): self._notes_txt.insert("1.0", a["notes"])

        self._err = tk.Label(body, text="", font=("Segoe UI",8),
                              fg=PAL["btn_red"], bg=PAL["bg"]); self._err.pack(anchor="w", pady=(8,0))
        brow = tk.Frame(body, bg=PAL["bg"]); brow.pack(fill="x", pady=(10,0))
        pill_btn(brow, "✓  Enregistrer", self._save, bg=PAL["btn_connect"], pady=9).pack(side="right")
        pill_btn(brow, "Annuler", back, bg=PAL["btn_gray"], pady=9).pack(side="right", padx=(0,8))
        if a and not is_new:
            pill_btn(brow, "🗑 Supprimer", self._delete, bg=PAL["btn_red"], pady=9).pack(side="left")

    def _save(self):
        v = {k: x.get().strip() for k, x in self.v.items()}
        if not v["rfid"] or not v["nom"]: self._err.config(text="RFID et Nom obligatoires."); return
        if v["enclos"]: self.db.enclos_ensure(self.site_id, v["enclos"])
        try: poids = float(v["poids"]) if v["poids"] else 0
        except: poids = 0
        kw = dict(rfid=v["rfid"], nom=v["nom"], espece=v["espece"],
                  sous_categorie=v["sous_categorie"], race=v["race"],
                  sexe=v["sexe"], dob=v["dob"], date_arrivee=v["date_arrivee"],
                  poids=poids, enclos=v["enclos"], pere=v["pere"], mere=v["mere"],
                  notes=self._notes_txt.get("1.0","end-1c"),
                  acquisition=1 if self.v_acq.get() else 0)
        if self.animal:
            self.db.upd_animal(self.animal["id"], **kw)
            self.app.goto("detail_animal", animal_id=self.animal["id"])
        else:
            aid = self.db.add_animal(self.site_id, kw["rfid"], kw["nom"], kw["espece"],
                                      kw["sous_categorie"], kw["race"], kw["sexe"], kw["dob"],
                                      kw["date_arrivee"], kw["poids"], kw["enclos"],
                                      kw["pere"], kw["mere"], acquisition=kw["acquisition"])
            self.app.goto("detail_animal", animal_id=aid)

    def _delete(self):
        if messagebox.askyesno("Supprimer","Supprimer cet animal ?"):
            self.db.del_animal(self.animal["id"]); self.app.goto("betail")


# ══════════════════════════════════════════════════════════════════════════════
#  DÉTAIL TRAITEMENT
# ══════════════════════════════════════════════════════════════════════════════
class DetailTraitementPage(Page):
    def __init__(self, parent, app, rfid, site_id):
        super().__init__(parent, app)
        self.rfid = rfid; self.site_id = site_id
        self.animal = self.db.get_animal(rfid=rfid)
        self._build()

    def _build(self):
        a = self.animal
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Retour", lambda: self.app.goto("detail_animal", animal_id=a["id"] if a else None),
                 bg="#444444", font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text=f"💊  Nouveau traitement — {a.get('nom','') if a else self.rfid}",
                 font=("Segoe UI",11,"bold"), fg="white", bg=PAL["bg_header"]).pack(side="left", padx=8)
        bc = f"→  Accueil  /  Bétail  /  {a.get('nom','') if a else self.rfid}  /  Traitement"
        tk.Label(top, text=bc, font=("Segoe UI",7), fg="#888888", bg=PAL["bg_header"], padx=16).pack(anchor="w", pady=(0,4))

        body = tk.Frame(self, bg=PAL["bg"], padx=60, pady=20); body.pack(fill="both", expand=True)
        tk.Label(body, text="Enregistrer un traitement", font=("Segoe UI",13,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(0,16))

        self._v_date = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self._v_trt  = tk.StringVar()
        self._v_pos  = tk.StringVar()
        self._v_dur  = tk.StringVar()
        self._v_notes = tk.StringVar()
        self._v_autres_trt = tk.StringVar()
        self._v_autres_pos = tk.StringVar()
        self._v_autres_dur = tk.StringVar()

        # Calendrier simplifié (champ texte avec label)
        date_card = card(body); date_card.pack(fill="x", pady=4)
        di = tk.Frame(date_card, bg=PAL["bg_card"], padx=14, pady=10); di.pack(fill="x")
        tk.Label(di, text="📅  Date du traitement", font=("Segoe UI",9,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_card"]).pack(anchor="w", pady=(0,6))
        entry_row(di, "Date *", self._v_date, PAL["bg_card"])
        tk.Label(di, text="Format : JJ/MM/AAAA", font=("Segoe UI",7),
                 fg=PAL["text_light"], bg=PAL["bg_card"]).pack(anchor="w")

        # Traitement
        trt_card = card(body); trt_card.pack(fill="x", pady=4)
        tri = tk.Frame(trt_card, bg=PAL["bg_card"], padx=14, pady=10); tri.pack(fill="x")
        tk.Label(tri, text="💊  Traitement", font=("Segoe UI",9,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_card"]).pack(anchor="w", pady=(0,6))
        trts = self.db.get_traitements_ref()
        combo_row(tri, "Traitement *", self._v_trt, trts, PAL["bg_card"])
        self._autres_trt_frame = tk.Frame(tri, bg=PAL["bg_card"]); self._autres_trt_frame.pack(fill="x")
        pill_btn(tri, "Autre...", lambda: self._toggle_autres(self._autres_trt_frame, self._v_trt, "trt"),
                 bg=PAL["btn_gray"], font=("Segoe UI",8), padx=10, pady=3).pack(anchor="w", pady=(4,0))

        # Posologie
        pos_card = card(body); pos_card.pack(fill="x", pady=4)
        pi = tk.Frame(pos_card, bg=PAL["bg_card"], padx=14, pady=10); pi.pack(fill="x")
        tk.Label(pi, text="⚗  Posologie", font=("Segoe UI",9,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_card"]).pack(anchor="w", pady=(0,6))
        combo_row(pi, "Posologie *", self._v_pos, POSOLOGIES_DB, PAL["bg_card"])
        self._autres_pos_frame = tk.Frame(pi, bg=PAL["bg_card"]); self._autres_pos_frame.pack(fill="x")
        pill_btn(pi, "Autre...", lambda: self._toggle_autres(self._autres_pos_frame, self._v_pos, "pos"),
                 bg=PAL["btn_gray"], font=("Segoe UI",8), padx=10, pady=3).pack(anchor="w", pady=(4,0))

        # Durée
        dur_card = card(body); dur_card.pack(fill="x", pady=4)
        dui = tk.Frame(dur_card, bg=PAL["bg_card"], padx=14, pady=10); dui.pack(fill="x")
        tk.Label(dui, text="⏱  Durée", font=("Segoe UI",9,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_card"]).pack(anchor="w", pady=(0,6))
        combo_row(dui, "Durée *", self._v_dur, DUREES_DB, PAL["bg_card"])
        self._autres_dur_frame = tk.Frame(dui, bg=PAL["bg_card"]); self._autres_dur_frame.pack(fill="x")
        pill_btn(dui, "Autre...", lambda: self._toggle_autres(self._autres_dur_frame, self._v_dur, "dur"),
                 bg=PAL["btn_gray"], font=("Segoe UI",8), padx=10, pady=3).pack(anchor="w", pady=(4,0))

        entry_row(body, "Notes", self._v_notes, PAL["bg"])
        self._err = tk.Label(body, text="", font=("Segoe UI",8), fg=PAL["btn_red"], bg=PAL["bg"])
        self._err.pack(anchor="w", pady=(8,0))

        bf = tk.Frame(body, bg=PAL["bg"], pady=10); bf.pack(fill="x")
        pill_btn(bf, "✓  Valider", self._save, bg=PAL["btn_connect"], pady=9).pack(side="right")
        pill_btn(bf, "Annuler", lambda: self.app.goto("detail_animal", animal_id=a["id"] if a else None),
                 bg=PAL["btn_gray"], pady=9).pack(side="right", padx=(0,8))

    def _toggle_autres(self, frame, var, kind):
        for w in frame.winfo_children(): w.destroy()
        v_new = tk.StringVar()
        ef = tk.Frame(frame, bg=PAL["bg_card"], highlightthickness=1, highlightbackground=PAL["border"])
        ef.pack(fill="x", pady=(6,0))
        e = tk.Entry(ef, textvariable=v_new, font=("Segoe UI",9), bg=PAL["bg_input"],
                     fg=PAL["text"], relief="flat")
        e.pack(side="left", fill="x", expand=True, padx=8, pady=6)
        def _apply():
            val = v_new.get().strip()
            if val:
                if kind == "trt":
                    self.db.add_traitement_ref(val)
                var.set(val)
        pill_btn(ef, "OK", _apply, bg=PAL["btn_blue"], font=("Segoe UI",8), padx=8, pady=4).pack(side="right", padx=4)

    def _save(self):
        if not self._v_date.get() or not self._v_trt.get():
            self._err.config(text="Date et traitement obligatoires."); return
        self.db.add_traitement(self.rfid, self.site_id, self._v_date.get(),
                               self._v_trt.get(), self._v_pos.get(),
                               self._v_dur.get(), self._v_notes.get())
        a = self.animal
        if a: self.app.goto("detail_animal", animal_id=a["id"])
        else: self.app.goto("traitements")


# ══════════════════════════════════════════════════════════════════════════════
#  DÉTAIL VACCIN
# ══════════════════════════════════════════════════════════════════════════════
class DetailVaccinPage(Page):
    def __init__(self, parent, app, rfid, site_id):
        super().__init__(parent, app)
        self.rfid = rfid; self.site_id = site_id
        self.animal = self.db.get_animal(rfid=rfid)
        self._build()

    def _build(self):
        a = self.animal
        espece = a.get("espece","bovin") if a else "bovin"
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Retour", lambda: self.app.goto("detail_animal", animal_id=a["id"] if a else None),
                 bg="#444444", font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text=f"💉  Nouveau vaccin — {a.get('nom','') if a else self.rfid}",
                 font=("Segoe UI",11,"bold"), fg="white", bg=PAL["bg_header"]).pack(side="left", padx=8)

        body = tk.Frame(self, bg=PAL["bg"], padx=60, pady=20); body.pack(fill="both", expand=True)
        tk.Label(body, text="Enregistrer une vaccination", font=("Segoe UI",13,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(0,16))

        self._v_date = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self._v_vacc = tk.StringVar(); self._v_pos = tk.StringVar(); self._v_dur = tk.StringVar()
        self._v_notes = tk.StringVar()

        # Date
        dc = card(body); dc.pack(fill="x", pady=4)
        di = tk.Frame(dc, bg=PAL["bg_card"], padx=14, pady=10); di.pack(fill="x")
        tk.Label(di, text="📅  Date du vaccin", font=("Segoe UI",9,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_card"]).pack(anchor="w", pady=(0,6))
        entry_row(di, "Date *", self._v_date, PAL["bg_card"])

        # Vaccin
        vc = card(body); vc.pack(fill="x", pady=4)
        vi = tk.Frame(vc, bg=PAL["bg_card"], padx=14, pady=10); vi.pack(fill="x")
        tk.Label(vi, text="💉  Vaccin", font=("Segoe UI",9,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_card"]).pack(anchor="w", pady=(0,6))
        vaccins = self.db.get_vaccins_ref(espece)
        combo_row(vi, "Vaccin *", self._v_vacc, vaccins, PAL["bg_card"])
        self._autres_v_f = tk.Frame(vi, bg=PAL["bg_card"]); self._autres_v_f.pack(fill="x")
        pill_btn(vi, "Autre...", lambda: self._toggle_autres(self._autres_v_f, self._v_vacc, espece),
                 bg=PAL["btn_gray"], font=("Segoe UI",8), padx=10, pady=3).pack(anchor="w", pady=(4,0))

        # Posologie + Durée
        pc = card(body); pc.pack(fill="x", pady=4)
        pci = tk.Frame(pc, bg=PAL["bg_card"], padx=14, pady=10); pci.pack(fill="x")
        combo_row(pci, "Posologie", self._v_pos, POSOLOGIES_DB, PAL["bg_card"])
        combo_row(pci, "Durée", self._v_dur, DUREES_DB, PAL["bg_card"])

        entry_row(body, "Notes", self._v_notes, PAL["bg"])
        self._err = tk.Label(body, text="", font=("Segoe UI",8), fg=PAL["btn_red"], bg=PAL["bg"])
        self._err.pack(anchor="w", pady=(8,0))

        bf = tk.Frame(body, bg=PAL["bg"], pady=10); bf.pack(fill="x")
        pill_btn(bf, "✓  Valider", self._save, bg=PAL["btn_connect"], pady=9).pack(side="right")
        pill_btn(bf, "Annuler", lambda: self.app.goto("detail_animal", animal_id=a["id"] if a else None),
                 bg=PAL["btn_gray"], pady=9).pack(side="right", padx=(0,8))

        # Historique bouton
        pill_btn(body, "📋 Voir historique complet",
                 lambda: self.app.goto("detail_animal", animal_id=a["id"] if a else None),
                 bg=PAL["btn_blue"], font=("Segoe UI",8), padx=12, pady=4).pack(anchor="w", pady=10)

    def _toggle_autres(self, frame, var, espece):
        for w in frame.winfo_children(): w.destroy()
        v_new = tk.StringVar()
        ef = tk.Frame(frame, bg=PAL["bg_card"], highlightthickness=1, highlightbackground=PAL["border"])
        ef.pack(fill="x", pady=(6,0))
        e = tk.Entry(ef, textvariable=v_new, font=("Segoe UI",9), bg=PAL["bg_input"],
                     fg=PAL["text"], relief="flat")
        e.pack(side="left", fill="x", expand=True, padx=8, pady=6)
        def _apply():
            val = v_new.get().strip()
            if val: self.db.add_vaccin_ref(val, espece); var.set(val)
        pill_btn(ef, "OK", _apply, bg=PAL["btn_blue"], font=("Segoe UI",8), padx=8, pady=4).pack(side="right", padx=4)

    def _save(self):
        if not self._v_date.get() or not self._v_vacc.get():
            self._err.config(text="Date et vaccin obligatoires."); return
        self.db.add_vaccination(self.rfid, self.site_id, self._v_date.get(),
                                self._v_vacc.get(), self._v_pos.get(),
                                self._v_dur.get(), self._v_notes.get())
        a = self.animal
        if a: self.app.goto("detail_animal", animal_id=a["id"])
        else: self.app.goto("vaccins")


# ══════════════════════════════════════════════════════════════════════════════
#  DÉTAIL ALIMENTATION
# ══════════════════════════════════════════════════════════════════════════════
class DetailAlimPage(Page):
    def __init__(self, parent, app, rfid, site_id):
        super().__init__(parent, app)
        self.rfid = rfid; self.site_id = site_id
        self.animal = self.db.get_animal(rfid=rfid)
        self._build()

    def _build(self):
        a = self.animal
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Retour", lambda: self.app.goto("detail_animal", animal_id=a["id"] if a else None),
                 bg="#444444", font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text=f"🌾  Alimentation — {a.get('nom','') if a else self.rfid}",
                 font=("Segoe UI",11,"bold"), fg="white", bg=PAL["bg_header"]).pack(side="left", padx=8)

        body = tk.Frame(self, bg=PAL["bg"], padx=60, pady=20); body.pack(fill="both", expand=True)
        tk.Label(body, text="Enregistrer un repas", font=("Segoe UI",13,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(0,16))

        self._v_date = tk.StringVar(value=datetime.now().strftime("%d/%m/%Y"))
        self._v_alim = tk.StringVar(); self._v_qte = tk.StringVar(value="0")
        self._v_unite = tk.StringVar(value="kg"); self._v_notes = tk.StringVar()

        dc = card(body); dc.pack(fill="x", pady=4)
        di = tk.Frame(dc, bg=PAL["bg_card"], padx=14, pady=10); di.pack(fill="x")
        entry_row(di, "Date *", self._v_date, PAL["bg_card"])

        ac = card(body); ac.pack(fill="x", pady=4)
        ai = tk.Frame(ac, bg=PAL["bg_card"], padx=14, pady=10); ai.pack(fill="x")
        alims = self.db.get_aliments_ref()
        combo_row(ai, "Aliment *", self._v_alim, alims, PAL["bg_card"])
        self._autres_a_f = tk.Frame(ai, bg=PAL["bg_card"]); self._autres_a_f.pack(fill="x")
        pill_btn(ai, "Autre...", lambda: self._toggle_autres(),
                 bg=PAL["btn_gray"], font=("Segoe UI",8), padx=10, pady=3).pack(anchor="w", pady=(4,0))
        entry_row(ai, "Quantité *", self._v_qte, PAL["bg_card"])
        combo_row(ai, "Unité", self._v_unite, UNITES_DB, PAL["bg_card"])
        entry_row(ai, "Notes", self._v_notes, PAL["bg_card"])

        self._err = tk.Label(body, text="", font=("Segoe UI",8), fg=PAL["btn_red"], bg=PAL["bg"])
        self._err.pack(anchor="w", pady=(8,0))
        bf = tk.Frame(body, bg=PAL["bg"], pady=10); bf.pack(fill="x")
        pill_btn(bf, "✓  Valider", self._save, bg=PAL["btn_connect"], pady=9).pack(side="right")
        pill_btn(bf, "Annuler", lambda: self.app.goto("detail_animal", animal_id=a["id"] if a else None),
                 bg=PAL["btn_gray"], pady=9).pack(side="right", padx=(0,8))

    def _toggle_autres(self):
        for w in self._autres_a_f.winfo_children(): w.destroy()
        v_new = tk.StringVar()
        ef = tk.Frame(self._autres_a_f, bg=PAL["bg_card"], highlightthickness=1, highlightbackground=PAL["border"])
        ef.pack(fill="x", pady=(6,0))
        e = tk.Entry(ef, textvariable=v_new, font=("Segoe UI",9), bg=PAL["bg_input"],
                     fg=PAL["text"], relief="flat")
        e.pack(side="left", fill="x", expand=True, padx=8, pady=6)
        def _apply():
            val = v_new.get().strip()
            if val: self.db.add_aliment_ref(val); self._v_alim.set(val)
        pill_btn(ef, "OK", _apply, bg=PAL["btn_blue"], font=("Segoe UI",8), padx=8, pady=4).pack(side="right", padx=4)

    def _save(self):
        if not self._v_alim.get():
            self._err.config(text="Aliment obligatoire."); return
        try: qte = float(self._v_qte.get())
        except: qte = 0
        self.db.add_alimentation(self.rfid, self.site_id, self._v_date.get(),
                                  self._v_alim.get(), qte, self._v_unite.get(), self._v_notes.get())
        a = self.animal
        if a: self.app.goto("detail_animal", animal_id=a["id"])
        else: self.app.goto("alimentation")


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE TRAITEMENTS — liste tous les animaux instables
# ══════════════════════════════════════════════════════════════════════════════
class TraitementsPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._site = get_current_site(app)
        self._build()

    def _build(self):
        self._mk_topbar("💊  Traitements")
        tb = tk.Frame(self, bg=PAL["bg_sect"]); tb.pack(fill="x")
        tbi = tk.Frame(tb, bg=PAL["bg_sect"], padx=12, pady=6); tbi.pack(fill="x")
        sf = tk.Frame(tbi, bg=PAL["bg_input"], highlightthickness=1, highlightbackground=PAL["border"])
        sf.pack(side="left")
        tk.Label(sf, text="🔍", bg=PAL["bg_input"], fg=PAL["text_sub"], font=("Segoe UI",9)).pack(side="left", padx=(8,4))
        self._v_search = tk.StringVar(); self._v_search.trace_add("write", lambda *_: self._filter())
        tk.Entry(sf, textvariable=self._v_search, font=("Segoe UI",9), bg=PAL["bg_input"],
                 fg=PAL["text"], relief="flat", width=22).pack(side="left", padx=(0,8), pady=5)

        paned = tk.Frame(self, bg=PAL["bg"]); paned.pack(fill="both", expand=True)
        left_panel = tk.Frame(paned, bg=PAL["bg_sidebar"], width=200)
        left_panel.pack(side="left", fill="y"); left_panel.pack_propagate(False)
        tk.Label(left_panel, text="Bêtes instables", font=("Segoe UI",9,"bold"),
                 fg=PAL["instable"], bg=PAL["bg_sidebar"], padx=10, pady=6).pack(anchor="w")
        sep(left_panel, PAL["border"])
        self._dot_frame = ScrollFrame(left_panel, PAL["bg_sidebar"])
        self._dot_frame.pack(fill="both", expand=True)
        self._table_frame = tk.Frame(paned, bg=PAL["bg_main"]); self._table_frame.pack(side="right", fill="both", expand=True)

        self._filter()

    def _mk_topbar(self, title):
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Accueil", lambda: self.app.goto("accueil"), bg="#444444",
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text=title, font=("Segoe UI",12,"bold"), fg="white", bg=PAL["bg_header"]).pack(side="left", padx=12)
        pill_btn(ti, "🐄 Bétail", lambda: self.app.goto("betail"), bg=PAL["btn_blue"],
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="right", padx=2)

    def _filter(self):
        if not self._site: return
        q = self._v_search.get().lower()
        animals = self.db.search_animals(self._site["id"], q=q, etat="instable")
        for w in self._dot_frame.inner.winfo_children(): w.destroy()
        for w in self._table_frame.winfo_children(): w.destroy()
        for a in animals:
            row = tk.Frame(self._dot_frame.inner, bg=PAL["bg_sidebar"], cursor="hand2")
            row.pack(fill="x", padx=8, pady=2)
            cv = status_dot(row, "instable", 12); cv.pack(side="left", padx=6, pady=6)
            tk.Label(row, text=a.get("nom","—")[:16], font=("Segoe UI",8),
                     fg=PAL["instable"], bg=PAL["bg_sidebar"], cursor="hand2").pack(side="left")
            for w in [row]: w.bind("<Button-1>", lambda e, r=a["rfid"], s=a["site_id"]:
                                   self.app.goto("detail_traitement", rfid=r, site_id=s))
        outer = tk.Frame(self._table_frame, bg=PAL["bg_main"]); outer.pack(fill="both", expand=True, padx=8, pady=6)
        cols = ("dot","rfid","nom","tc","date_last","etat")
        hdrs = {"dot":"●","rfid":"Tag RFID","nom":"Nom","tc":"Temp °C","date_last":"Dernière mesure","etat":"État"}
        widths = {"dot":30,"rfid":120,"nom":130,"tc":80,"date_last":140,"etat":100}
        tree = ttk.Treeview(outer, columns=cols, show="headings", height=25)
        for c in cols: tree.heading(c, text=hdrs[c]); tree.column(c, width=widths.get(c,90), anchor="w" if c=="nom" else "center")
        tree.tag_configure("instable", foreground=PAL["instable"])
        for a in animals:
            lt = self.db.last_temp(a["rfid"])
            tc = lt["tc"] if lt else None; ts = lt["ts"] if lt else ""
            tree.insert("","end",iid=str(a["id"]),tags=("instable",),
                values=("●",a.get("rfid",""),a.get("nom","—"),
                        f"{tc:.1f}" if tc else "—", (ts or "")[:16], "● Instable"))
        vsb = ttk.Scrollbar(outer, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set); vsb.pack(side="right",fill="y"); tree.pack(fill="both",expand=True)
        tree.bind("<Double-Button-1>", lambda e: self._open(tree))

    def _open(self, tree):
        sel = tree.selection()
        if sel:
            a = self.db.get_animal(aid=int(sel[0]))
            if a: self.app.goto("detail_traitement", rfid=a["rfid"], site_id=a["site_id"])


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE VACCINS — liste toutes les bêtes
# ══════════════════════════════════════════════════════════════════════════════
class VaccinsPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._site = get_current_site(app)
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Accueil", lambda: self.app.goto("accueil"), bg="#444444",
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text="💉  Vaccinations", font=("Segoe UI",12,"bold"),
                 fg="white", bg=PAL["bg_header"]).pack(side="left", padx=12)

        tb = tk.Frame(self, bg=PAL["bg_sect"]); tb.pack(fill="x")
        tbi = tk.Frame(tb, bg=PAL["bg_sect"], padx=12, pady=6); tbi.pack(fill="x")
        sf = tk.Frame(tbi, bg=PAL["bg_input"], highlightthickness=1, highlightbackground=PAL["border"])
        sf.pack(side="left")
        tk.Label(sf, text="🔍", bg=PAL["bg_input"], fg=PAL["text_sub"], font=("Segoe UI",9)).pack(side="left", padx=(8,4))
        self._v_search = tk.StringVar(); self._v_search.trace_add("write", lambda *_: self._filter())
        tk.Entry(sf, textvariable=self._v_search, font=("Segoe UI",9), bg=PAL["bg_input"],
                 fg=PAL["text"], relief="flat", width=22).pack(side="left", padx=(0,8), pady=5)

        paned = tk.Frame(self, bg=PAL["bg"]); paned.pack(fill="both", expand=True)
        left_panel = tk.Frame(paned, bg=PAL["bg_sidebar"], width=200)
        left_panel.pack(side="left", fill="y"); left_panel.pack_propagate(False)
        tk.Label(left_panel, text="Bêtes", font=("Segoe UI",9,"bold"),
                 fg=PAL["text_sub"], bg=PAL["bg_sidebar"], padx=10, pady=6).pack(anchor="w")
        sep(left_panel, PAL["border"])
        self._dot_frame = ScrollFrame(left_panel, PAL["bg_sidebar"])
        self._dot_frame.pack(fill="both", expand=True)
        self._table_frame = tk.Frame(paned, bg=PAL["bg_main"])
        self._table_frame.pack(side="right", fill="both", expand=True)

        self._filter()

    def _filter(self):
        if not self._site: return
        q = self._v_search.get().lower()
        animals = self.db.search_animals(self._site["id"], q=q)
        for w in self._dot_frame.inner.winfo_children(): w.destroy()
        for w in self._table_frame.winfo_children(): w.destroy()
        for a in animals:
            row = tk.Frame(self._dot_frame.inner, bg=PAL["bg_sidebar"], cursor="hand2")
            row.pack(fill="x", padx=8, pady=2)
            cv = status_dot(row, a.get("statut_etat","stable"), 12); cv.pack(side="left", padx=6, pady=6)
            tk.Label(row, text=a.get("nom","—")[:16], font=("Segoe UI",8),
                     fg=PAL["text"], bg=PAL["bg_sidebar"]).pack(side="left")
            for w2 in [row, cv]: w2.bind("<Button-1>", lambda e, r=a["rfid"], s=a["site_id"]:
                                         self.app.goto("detail_vaccin", rfid=r, site_id=s))

        outer = tk.Frame(self._table_frame, bg=PAL["bg_main"]); outer.pack(fill="both", expand=True, padx=8, pady=6)
        cols = ("dot","rfid","nom","espece","dernier_vaccin","date")
        hdrs = {"dot":"●","rfid":"Tag RFID","nom":"Nom","espece":"Espèce","dernier_vaccin":"Dernier vaccin","date":"Date"}
        tree = ttk.Treeview(outer, columns=cols, show="headings", height=25)
        for c in cols: tree.heading(c, text=hdrs[c]); tree.column(c, width=110, anchor="w" if c in("nom","espece","dernier_vaccin") else "center")
        for a in animals:
            vacc_rows = self.db.get_vaccinations(rfid=a["rfid"])
            last_v = vacc_rows[0] if vacc_rows else None
            etat = a.get("statut_etat","stable")
            tag_col = {"stable":"stable","instable":"instable","traitement":"traitement"}.get(etat,"stable")
            tree.tag_configure("stable", foreground=PAL["stable"])
            tree.tag_configure("instable", foreground=PAL["instable"])
            tree.tag_configure("traitement", foreground=PAL["traitement"])
            tree.insert("","end",iid=str(a["id"]),tags=(tag_col,),
                values=("●",a.get("rfid",""),a.get("nom","—"),
                        ESPECE_LABEL.get(a.get("espece",""),"—"),
                        last_v["vaccin"] if last_v else "—",
                        last_v["date_vaccin"] if last_v else "—"))
        vsb = ttk.Scrollbar(outer, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set); vsb.pack(side="right",fill="y"); tree.pack(fill="both",expand=True)
        tree.bind("<Double-Button-1>", lambda e: self._open(tree))

    def _open(self, tree):
        sel = tree.selection()
        if sel:
            a = self.db.get_animal(aid=int(sel[0]))
            if a: self.app.goto("detail_vaccin", rfid=a["rfid"], site_id=a["site_id"])


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE GROSSESSE
# ══════════════════════════════════════════════════════════════════════════════
class GrossessePage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._site = get_current_site(app)
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Accueil", lambda: self.app.goto("accueil"), bg="#444444",
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text="🤰  Suivi des Gestations", font=("Segoe UI",12,"bold"),
                 fg="white", bg=PAL["bg_header"]).pack(side="left", padx=12)

        if not self._site: return
        rows = self.db.get_gestations(site_id=self._site["id"])
        en_cours = [r for r in rows if r.get("statut","en_cours")=="en_cours"]
        terminees = [r for r in rows if r.get("statut","en_cours")=="terminee"]

        sf = ScrollFrame(self, PAL["bg"]); sf.pack(fill="both", expand=True)
        body = sf.inner
        pad = tk.Frame(body, bg=PAL["bg"], padx=20, pady=16); pad.pack(fill="both", expand=True)

        def sect_gest(title, data, col):
            tk.Label(pad, text=title, font=("Segoe UI",11,"bold"),
                     fg=col, bg=PAL["bg"]).pack(anchor="w", pady=(12,4))
            if not data:
                tk.Label(pad, text="Aucune gestation.", font=("Segoe UI",8),
                         fg=PAL["text_light"], bg=PAL["bg"]).pack(anchor="w", padx=8)
                return
            tbl = card(pad); tbl.pack(fill="x", pady=4)
            ti_f = tk.Frame(tbl, bg=PAL["bg_sect"]); ti_f.pack(fill="x")
            for h, w in [("Bête",140),("Saillie",100),("Prévue",100),("Réelle",100),("Petits",60),("Notes",200)]:
                tk.Label(ti_f, text=h, font=("Segoe UI",7,"bold"), fg=PAL["text_sub"],
                         bg=PAL["bg_sect"], width=w//7, anchor="w", padx=8, pady=4).pack(side="left")
            for r in data:
                row = tk.Frame(tbl, bg=PAL["bg_main"]); row.pack(fill="x")
                ri  = tk.Frame(row, bg=PAL["bg_main"], padx=8, pady=5); ri.pack(fill="x")
                for txt in [r.get("nom","") or r.get("rfid",""),
                            r.get("date_saillie","—"), r.get("date_naissance_prevue","—"),
                            r.get("date_naissance_reelle","—") or "—",
                            str(r.get("nb_petits",1)), r.get("notes","")]:
                    tk.Label(ri, text=txt, font=("Segoe UI",8), fg=PAL["text"],
                             bg=PAL["bg_main"], width=14, anchor="w").pack(side="left", padx=(0,8))
                sep(tbl, PAL["border"])

        sect_gest(f"⏳ Gestations en cours ({len(en_cours)})", en_cours, "#E91E63")
        sect_gest(f"✓ Gestations terminées ({len(terminees)})", terminees, PAL["stable"])


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE ALIMENTATION globale
# ══════════════════════════════════════════════════════════════════════════════
class AlimentationPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._site = get_current_site(app)
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Accueil", lambda: self.app.goto("accueil"), bg="#444444",
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text="🌾  Suivi de l'Alimentation", font=("Segoe UI",12,"bold"),
                 fg="white", bg=PAL["bg_header"]).pack(side="left", padx=12)

        if not self._site: return
        sf = ScrollFrame(self, PAL["bg"]); sf.pack(fill="both", expand=True)
        body = sf.inner
        pad = tk.Frame(body, bg=PAL["bg"], padx=20, pady=16); pad.pack(fill="both", expand=True)

        tk.Label(pad, text="Repas des 7 derniers jours", font=("Segoe UI",11,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(0,8))

        rows = self.db.get_alimentation(site_id=self._site["id"], days=7)
        if not rows:
            tk.Label(pad, text="Aucun repas enregistré.",
                     font=("Segoe UI",9), fg=PAL["text_light"], bg=PAL["bg"]).pack(anchor="w")
            return

        tbl = card(pad); tbl.pack(fill="x")
        hdr = tk.Frame(tbl, bg=PAL["bg_sect"]); hdr.pack(fill="x")
        for h in ["Date","Bête","Aliment","Quantité","Unité","Notes"]:
            tk.Label(hdr, text=h, font=("Segoe UI",7,"bold"), fg=PAL["text_sub"],
                     bg=PAL["bg_sect"], width=12, anchor="w", padx=8, pady=4).pack(side="left")
        for r in rows:
            row = tk.Frame(tbl, bg=PAL["bg_main"]); row.pack(fill="x")
            ri  = tk.Frame(row, bg=PAL["bg_main"], padx=8, pady=5); ri.pack(fill="x")
            for txt in [r.get("date_repas","—"), r.get("nom","") or r.get("rfid",""),
                        r.get("aliment","—"), str(r.get("quantite",0)),
                        r.get("unite","—"), r.get("notes","")]:
                tk.Label(ri, text=txt, font=("Segoe UI",8), fg=PAL["text"],
                         bg=PAL["bg_main"], width=12, anchor="w").pack(side="left", padx=(0,8))
            sep(tbl, PAL["border"])


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE STATISTIQUES
# ══════════════════════════════════════════════════════════════════════════════
class StatsPage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._site = get_current_site(app)
        self._build()

    def _build(self):
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Accueil", lambda: self.app.goto("accueil"), bg="#444444",
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text="📊  Statistiques & Tableaux de bord", font=("Segoe UI",12,"bold"),
                 fg="white", bg=PAL["bg_header"]).pack(side="left", padx=12)
        pill_btn(ti, "↻ Actualiser", self._refresh, bg=PAL["btn_blue"],
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="right")

        # Tab selector
        tab_bar = tk.Frame(self, bg=PAL["bg_sect"]); tab_bar.pack(fill="x")
        self._tab_btns = {}
        for tn, tl in [("overview","Vue globale"),("temperatures","Températures"),
                        ("traitements","Traitements"),("vaccinations","Vaccinations")]:
            b = tk.Button(tab_bar, text=tl, font=("Segoe UI",8,"bold"),
                          fg=PAL["text_sub"], bg=PAL["bg_sect"], relief="flat",
                          padx=14, pady=7, cursor="hand2",
                          command=lambda t=tn: self._show_tab(t))
            b.pack(side="left"); self._tab_btns[tn] = b

        self._tcontent = tk.Frame(self, bg=PAL["bg"]); self._tcontent.pack(fill="both", expand=True)
        self._show_tab("overview")

    def _show_tab(self, tab):
        for t, b in self._tab_btns.items():
            b.config(bg=PAL["btn_purple"] if t==tab else PAL["bg_sect"],
                     fg="white" if t==tab else PAL["text_sub"])
        for w in self._tcontent.winfo_children(): w.destroy()
        {"overview":self._t_overview,"temperatures":self._t_temp,
         "traitements":self._t_trt,"vaccinations":self._t_vacc}[tab]()

    def _refresh(self):
        self._site = get_current_site(self.app)
        # re-show current tab
        for t, b in self._tab_btns.items():
            if b.cget("bg") == PAL["btn_purple"]: self._show_tab(t); return

    def _t_overview(self):
        sf = ScrollFrame(self._tcontent, PAL["bg"]); sf.pack(fill="both", expand=True)
        body = tk.Frame(sf.inner, bg=PAL["bg"], padx=20, pady=16); body.pack(fill="x")
        if not self._site:
            tk.Label(body, text="Aucun site.", fg=PAL["text_light"], bg=PAL["bg"],
                     font=("Segoe UI",9)).pack(); return
        sid = self._site["id"]
        stats = self.db.current_animal_stats(sid)
        total = self.db._q("SELECT COUNT(*) FROM animals WHERE site_id=?", (sid,)).fetchone()[0]

        tk.Label(body, text="Vue globale du troupeau", font=("Segoe UI",12,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(0,12))

        cards_row = tk.Frame(body, bg=PAL["bg"]); cards_row.pack(fill="x", pady=(0,16))
        for lbl, val, col in [
            ("Total animaux", total, PAL["btn_blue"]),
            ("État Normal", stats.get("Normal",0), PAL["stable"]),
            ("Fièvre", stats.get("Fievre",0), PAL["btn_red"]),
            ("Hypothermie", stats.get("Hypothermie",0), "#3498DB"),
            ("En chaleur", stats.get("En chaleur",0), "#E91E63"),
            ("Sans mesure", stats.get("Sans mesure",0), PAL["btn_gray"]),
        ]:
            f = card(cards_row); f.pack(side="left", padx=(0,8), ipadx=12, ipady=8)
            tk.Label(f, text=str(val), font=("Segoe UI",24,"bold"), fg=col, bg=PAL["bg_card"]).pack()
            tk.Label(f, text=lbl, font=("Segoe UI",7,"bold"), fg=PAL["text_light"], bg=PAL["bg_card"]).pack()

        # Distribution par espèce
        tk.Label(body, text="Distribution par espèce", font=("Segoe UI",10,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(8,6))
        esp_frame = card(body); esp_frame.pack(fill="x")
        for esp, label in ESPECE_LABEL.items():
            cnt = self.db._q("SELECT COUNT(*) FROM animals WHERE site_id=? AND espece=?", (sid,esp)).fetchone()[0]
            if cnt == 0: continue
            row = tk.Frame(esp_frame, bg=PAL["bg_card"]); row.pack(fill="x", padx=12, pady=4)
            tk.Label(row, text=f"{ESPECE_ICON[esp]} {label}", font=("Segoe UI",9),
                     fg=PAL["text"], bg=PAL["bg_card"], width=14, anchor="w").pack(side="left")
            # Barre
            bar_outer = tk.Frame(row, bg=PAL["border"], height=16); bar_outer.pack(side="left", fill="x", expand=True, padx=(8,8))
            bar_outer.pack_propagate(False)
            bar_w = int((cnt/max(total,1))*200)
            bar_inner = tk.Frame(bar_outer, bg=PAL["btn_blue"], height=16, width=max(bar_w,4))
            bar_inner.pack(side="left"); bar_inner.pack_propagate(False)
            tk.Label(row, text=str(cnt), font=("Segoe UI",8,"bold"),
                     fg=PAL["btn_blue"], bg=PAL["bg_card"]).pack(side="right")

        # Moyennes 24h
        tk.Label(body, text="Moyennes de température (24h)", font=("Segoe UI",10,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(16,6))
        avgs = self.db.avgs_24h(sid)
        if not avgs:
            tk.Label(body, text="Aucune donnée.", font=("Segoe UI",8),
                     fg=PAL["text_light"], bg=PAL["bg"]).pack(anchor="w"); return
        avg_card = card(body); avg_card.pack(fill="x")
        hdrc = tk.Frame(avg_card, bg=PAL["bg_sect"]); hdrc.pack(fill="x")
        for txt, w in [("Animal",140),("Moy °C",80),("Min",70),("Max",70),("Mesures",70)]:
            tk.Label(hdrc, text=txt, font=("Segoe UI",7,"bold"), fg=PAL["text_sub"],
                     bg=PAL["bg_sect"], width=w//7, anchor="w", padx=8, pady=4).pack(side="left")
        for r in avgs:
            st = get_status(r["avg"], r.get("sexe","F"))
            col = {"Fievre":PAL["btn_red"],"Hypothermie":PAL["btn_blue"],"Elevee":PAL["btn_orange"]}.get(st, PAL["text"])
            bg_ = "#FFF0F0" if st=="Fievre" else PAL["bg_main"]
            row = tk.Frame(avg_card, bg=bg_); row.pack(fill="x")
            ri  = tk.Frame(row, bg=bg_, padx=8, pady=4); ri.pack(fill="x")
            tk.Label(ri, text=f"{ESPECE_ICON.get(r.get('espece','bovin'),'🐄')} {r['nom'] or r['rfid']}",
                     font=("Segoe UI",8), fg=PAL["text"], bg=bg_, width=18, anchor="w").pack(side="left")
            for val, c in [(f"{r['avg']:.2f}",col),(f"{r['min']:.1f}",col),
                           (f"{r['max']:.1f}",col),(str(r["cnt"]),PAL["text_sub"])]:
                tk.Label(ri, text=val, font=("Segoe UI",8,"bold"), fg=c,
                         bg=bg_, width=8, anchor="w").pack(side="left")
            sep(avg_card, PAL["border"])

    def _t_temp(self):
        if not MPLOT or not self._site:
            tk.Label(self._tcontent, text="Données non disponibles.", fg=PAL["text_sub"],
                     bg=PAL["bg"], font=("Segoe UI",9)).pack(expand=True); return
        sid = self._site["id"]
        avgs = self.db.avgs_24h(sid)
        if not avgs:
            tk.Label(self._tcontent, text="Aucune donnée de température (24h).",
                     fg=PAL["text_light"], bg=PAL["bg"], font=("Segoe UI",9)).pack(expand=True); return
        names  = [r["nom"] or r["rfid"] for r in avgs]
        moyens = [r["avg"] for r in avgs]
        fig = Figure(figsize=(8,4), dpi=96, facecolor=PAL["bg_main"])
        ax  = fig.add_subplot(111, facecolor=PAL["bg_sect"])
        fig.subplots_adjust(left=0.08, right=0.97, top=0.88, bottom=0.22)
        colors_bar = [PAL["btn_red"] if m>TEMP_HIGH else (PAL["btn_orange"] if m>TEMP_NORM else PAL["stable"]) for m in moyens]
        bars = ax.bar(range(len(names)), moyens, color=colors_bar, edgecolor="white", width=0.7)
        ax.axhline(TEMP_HIGH, lw=1.5, ls="--", color=PAL["btn_red"], alpha=0.6, label="Fièvre")
        ax.axhline(TEMP_NORM, lw=1.5, ls="--", color=PAL["stable"], alpha=0.6, label="Normal")
        ax.set_xticks(range(len(names))); ax.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
        ax.set_ylabel("°C", fontsize=9, color=PAL["text_sub"])
        ax.tick_params(colors=PAL["text_sub"], labelsize=8)
        ax.set_title("Température moyenne par animal (24h)", fontsize=10, color=PAL["text"], pad=8)
        for sp in ax.spines.values(): sp.set_color(PAL["border"])
        ax.grid(True, alpha=0.3, color=PAL["border"], axis="y")
        if moyens:
            m = max(0.5,(max(moyens)-min(moyens))*0.25)
            ax.set_ylim(min(moyens)-m, max(moyens)+m)
        cvs = FigureCanvasTkAgg(fig, master=self._tcontent)
        cvs.draw(); cvs.get_tk_widget().pack(fill="both", expand=True)

    def _t_trt(self):
        if not self._site: return
        sf = ScrollFrame(self._tcontent, PAL["bg"]); sf.pack(fill="both", expand=True)
        body = tk.Frame(sf.inner, bg=PAL["bg"], padx=20, pady=16); body.pack(fill="x")
        tk.Label(body, text="Derniers traitements", font=("Segoe UI",11,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(0,8))
        rows = self.db.get_traitements(site_id=self._site["id"])
        if not rows:
            tk.Label(body, text="Aucun traitement.", fg=PAL["text_light"], bg=PAL["bg"],
                     font=("Segoe UI",8)).pack(anchor="w"); return
        tbl = card(body); tbl.pack(fill="x")
        hdr = tk.Frame(tbl, bg=PAL["bg_sect"]); hdr.pack(fill="x")
        for h in ["Date","Bête","Traitement","Posologie","Durée"]:
            tk.Label(hdr, text=h, font=("Segoe UI",7,"bold"), fg=PAL["text_sub"],
                     bg=PAL["bg_sect"], width=12, anchor="w", padx=8, pady=4).pack(side="left")
        for r in rows[:30]:
            row = tk.Frame(tbl, bg=PAL["bg_main"]); row.pack(fill="x")
            ri  = tk.Frame(row, bg=PAL["bg_main"], padx=8, pady=4); ri.pack(fill="x")
            for txt in [r.get("date_traitement","—"), r.get("nom","") or r.get("rfid",""),
                        r.get("traitement","—"), r.get("posologie","—"), r.get("duree","—")]:
                tk.Label(ri, text=txt, font=("Segoe UI",8), fg=PAL["text"],
                         bg=PAL["bg_main"], width=12, anchor="w").pack(side="left", padx=(0,8))
            sep(tbl, PAL["border"])

    def _t_vacc(self):
        if not self._site: return
        sf = ScrollFrame(self._tcontent, PAL["bg"]); sf.pack(fill="both", expand=True)
        body = tk.Frame(sf.inner, bg=PAL["bg"], padx=20, pady=16); body.pack(fill="x")
        tk.Label(body, text="Dernières vaccinations", font=("Segoe UI",11,"bold"),
                 fg=PAL["text"], bg=PAL["bg"]).pack(anchor="w", pady=(0,8))
        rows = self.db.get_vaccinations(site_id=self._site["id"])
        if not rows:
            tk.Label(body, text="Aucune vaccination.", fg=PAL["text_light"], bg=PAL["bg"],
                     font=("Segoe UI",8)).pack(anchor="w"); return
        tbl = card(body); tbl.pack(fill="x")
        hdr = tk.Frame(tbl, bg=PAL["bg_sect"]); hdr.pack(fill="x")
        for h in ["Date","Bête","Vaccin","Posologie","Durée"]:
            tk.Label(hdr, text=h, font=("Segoe UI",7,"bold"), fg=PAL["text_sub"],
                     bg=PAL["bg_sect"], width=12, anchor="w", padx=8, pady=4).pack(side="left")
        for r in rows[:30]:
            row = tk.Frame(tbl, bg=PAL["bg_main"]); row.pack(fill="x")
            ri  = tk.Frame(row, bg=PAL["bg_main"], padx=8, pady=4); ri.pack(fill="x")
            for txt in [r.get("date_vaccin","—"), r.get("nom","") or r.get("rfid",""),
                        r.get("vaccin","—"), r.get("posologie","—"), r.get("duree","—")]:
                tk.Label(ri, text=txt, font=("Segoe UI",8), fg=PAL["text"],
                         bg=PAL["bg_main"], width=12, anchor="w").pack(side="left", padx=(0,8))
            sep(tbl, PAL["border"])


# ══════════════════════════════════════════════════════════════════════════════
#  BACK-OFFICE
# ══════════════════════════════════════════════════════════════════════════════
class BackOfficePage(Page):
    def __init__(self, parent, app):
        super().__init__(parent, app); self._build()

    def _build(self):
        top = tk.Frame(self, bg=PAL["bg_header"]); top.pack(fill="x")
        ti  = tk.Frame(top, bg=PAL["bg_header"], padx=14, pady=8); ti.pack(fill="x")
        pill_btn(ti, "← Accueil", lambda: self.app.goto("accueil"), bg="#444444",
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="left")
        tk.Label(ti, text="⚙  Back-office — Administration", font=("Segoe UI",12,"bold"),
                 fg="white", bg=PAL["bg_header"]).pack(side="left", padx=12)

        tab_bar = tk.Frame(self, bg=PAL["bg_sect"]); tab_bar.pack(fill="x")
        self._tab_btns = {}
        tabs_def = [("betail","🐄 Bétail"),("vaccins_ref","💉 Vaccins"),
                    ("trt_ref","💊 Traitements"),("alim_ref","🌾 Aliments"),("users","👥 Utilisateurs")]
        for tn, tl in tabs_def:
            b = tk.Button(tab_bar, text=tl, font=("Segoe UI",8,"bold"),
                          fg=PAL["text_sub"], bg=PAL["bg_sect"], relief="flat",
                          padx=14, pady=7, cursor="hand2",
                          command=lambda t=tn: self._show_tab(t))
            b.pack(side="left"); self._tab_btns[tn] = b

        self._tcontent = tk.Frame(self, bg=PAL["bg"]); self._tcontent.pack(fill="both", expand=True)
        self._show_tab("betail")

    def _show_tab(self, tab):
        for t, b in self._tab_btns.items():
            b.config(bg=PAL["btn_gray"] if t==tab else PAL["bg_sect"],
                     fg="white" if t==tab else PAL["text_sub"])
        for w in self._tcontent.winfo_children(): w.destroy()
        {"betail":self._t_betail,"vaccins_ref":self._t_vaccref,
         "trt_ref":self._t_trtref,"alim_ref":self._t_alimref,"users":self._t_users}[tab]()

    def _t_betail(self):
        site = get_current_site(self.app)
        if not site:
            tk.Label(self._tcontent, text="Aucun site.", fg=PAL["text_light"], bg=PAL["bg"],
                     font=("Segoe UI",9)).pack(expand=True); return
        body = tk.Frame(self._tcontent, bg=PAL["bg"]); body.pack(fill="both", expand=True)
        hdr = tk.Frame(body, bg=PAL["bg_sect"], padx=16, pady=8); hdr.pack(fill="x")
        tk.Label(hdr, text=f"Gestion du bétail — {site['nom']}", font=("Segoe UI",10,"bold"),
                 fg=PAL["text"], bg=PAL["bg_sect"]).pack(side="left")
        pill_btn(hdr, "+ Ajouter", lambda: self.app.goto("edit_animal", animal_id=None, site_id=site["id"]),
                 bg=PAL["btn_green"], font=("Segoe UI",8), padx=10, pady=3).pack(side="right")
        sep(body, PAL["border"])
        sf = ScrollFrame(body, PAL["bg"]); sf.pack(fill="both", expand=True)
        animals = self.db.get_animals(site["id"])
        for a in animals:
            row = tk.Frame(sf.inner, bg=PAL["bg_main"]); row.pack(fill="x")
            ri  = tk.Frame(row, bg=PAL["bg_main"], padx=12, pady=6); ri.pack(fill="x")
            tk.Label(ri, text=f"{ESPECE_ICON.get(a.get('espece','bovin'),'🐄')} {a.get('nom','—')}",
                     font=("Segoe UI",9), fg=PAL["text"], bg=PAL["bg_main"],
                     width=20, anchor="w").pack(side="left")
            tk.Label(ri, text=a.get("rfid",""), font=("Segoe UI",8), fg=PAL["text_sub"],
                     bg=PAL["bg_main"], width=14, anchor="w").pack(side="left", padx=(8,0))
            tk.Label(ri, text=a.get("sous_categorie","—"), font=("Segoe UI",8),
                     fg=PAL["text_sub"], bg=PAL["bg_main"], width=16, anchor="w").pack(side="left")
            pill_btn(ri, "✏", lambda aid=a["id"]: self.app.goto("edit_animal", animal_id=aid, site_id=site["id"]),
                     bg=PAL["btn_blue"], font=("Segoe UI",8), padx=8, pady=2).pack(side="right", padx=2)
            pill_btn(ri, "🗑", lambda aid=a["id"], an=a.get("nom",""):
                     self._del_animal(aid, an), bg=PAL["btn_red"],
                     font=("Segoe UI",8), padx=8, pady=2).pack(side="right")
            sep(sf.inner, PAL["border"])

    def _del_animal(self, aid, nom):
        if messagebox.askyesno("Supprimer", f"Supprimer '{nom}' ?"):
            self.db.del_animal(aid); self._show_tab("betail")

    def _t_ref(self, title, get_fn, add_fn, del_fn):
        body = tk.Frame(self._tcontent, bg=PAL["bg"]); body.pack(fill="both", expand=True)
        hdr = tk.Frame(body, bg=PAL["bg_sect"], padx=16, pady=8); hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=("Segoe UI",10,"bold"),
                 fg=PAL["text"], bg=PAL["bg_sect"]).pack(side="left")
        v_new = tk.StringVar()
        ef = tk.Frame(hdr, bg=PAL["bg_input"], highlightthickness=1, highlightbackground=PAL["border"])
        ef.pack(side="right")
        tk.Entry(ef, textvariable=v_new, font=("Segoe UI",9), bg=PAL["bg_input"],
                 fg=PAL["text"], relief="flat", width=18).pack(side="left", padx=6, pady=4)
        def _add():
            if v_new.get().strip(): add_fn(v_new.get()); v_new.set(""); self._refresh_ref(body, get_fn, del_fn)
        pill_btn(hdr, "+ Ajouter", _add, bg=PAL["btn_green"], font=("Segoe UI",8), padx=10, pady=4).pack(side="right", padx=(0,8))
        sep(body, PAL["border"])
        self._ref_list = tk.Frame(body, bg=PAL["bg"]); self._ref_list.pack(fill="both", expand=True)
        self._refresh_ref(body, get_fn, del_fn)

    def _refresh_ref(self, body, get_fn, del_fn):
        for w in self._ref_list.winfo_children(): w.destroy()
        sf = ScrollFrame(self._ref_list, PAL["bg"]); sf.pack(fill="both", expand=True)
        for nom in get_fn():
            row = tk.Frame(sf.inner, bg=PAL["bg_main"]); row.pack(fill="x")
            ri  = tk.Frame(row, bg=PAL["bg_main"], padx=12, pady=6); ri.pack(fill="x")
            tk.Label(ri, text=nom, font=("Segoe UI",9), fg=PAL["text"],
                     bg=PAL["bg_main"]).pack(side="left")
            pill_btn(ri, "🗑", lambda n=nom: (del_fn(n), self._refresh_ref(body, get_fn, del_fn)),
                     bg=PAL["btn_red"], font=("Segoe UI",8), padx=8, pady=2).pack(side="right")
            sep(sf.inner, PAL["border"])

    def _t_vaccref(self):
        def del_v(nom): self.db._w("DELETE FROM vaccins_ref WHERE nom=?", (nom,))
        self._t_ref("Gestion des vaccins", self.db.get_vaccins_ref,
                    lambda n: self.db.add_vaccin_ref(n), del_v)

    def _t_trtref(self):
        def del_t(nom): self.db._w("DELETE FROM traitements_ref WHERE nom=?", (nom,))
        self._t_ref("Gestion des traitements", self.db.get_traitements_ref,
                    lambda n: self.db.add_traitement_ref(n), del_t)

    def _t_alimref(self):
        def del_a(nom): self.db._w("DELETE FROM aliments_ref WHERE nom=?", (nom,))
        self._t_ref("Gestion des aliments", self.db.get_aliments_ref,
                    lambda n: self.db.add_aliment_ref(n), del_a)

    def _t_users(self):
        body = tk.Frame(self._tcontent, bg=PAL["bg"]); body.pack(fill="both", expand=True)
        hdr = tk.Frame(body, bg=PAL["bg_sect"], padx=16, pady=8); hdr.pack(fill="x")
        tk.Label(hdr, text="Gestion des utilisateurs", font=("Segoe UI",10,"bold"),
                 fg=PAL["text"], bg=PAL["bg_sect"]).pack(side="left")
        pill_btn(hdr, "+ Ajouter", self._add_user_dlg, bg=PAL["btn_green"],
                 font=("Segoe UI",8), padx=10, pady=3).pack(side="right")
        sep(body, PAL["border"])
        sf = ScrollFrame(body, PAL["bg"]); sf.pack(fill="both", expand=True)
        users = self.db.get_all_users()
        hdr2 = tk.Frame(sf.inner, bg=PAL["bg_sect"]); hdr2.pack(fill="x")
        for h in ["Prénom","Nom","Email","Rôle",""]:
            tk.Label(hdr2, text=h, font=("Segoe UI",7,"bold"), fg=PAL["text_sub"],
                     bg=PAL["bg_sect"], width=12, anchor="w", padx=8, pady=4).pack(side="left")
        for u in users:
            row = tk.Frame(sf.inner, bg=PAL["bg_main"]); row.pack(fill="x")
            ri  = tk.Frame(row, bg=PAL["bg_main"], padx=8, pady=6); ri.pack(fill="x")
            for txt in [u.get("prenom",""), u.get("nom",""), u.get("email",""), u.get("role","user")]:
                tk.Label(ri, text=txt, font=("Segoe UI",8), fg=PAL["text"],
                         bg=PAL["bg_main"], width=12, anchor="w").pack(side="left", padx=(0,8))
            if u["id"] != self.user["id"]:
                pill_btn(ri, "🗑", lambda uid=u["id"]: self._del_user(uid),
                         bg=PAL["btn_red"], font=("Segoe UI",8), padx=8, pady=2).pack(side="right")
            sep(sf.inner, PAL["border"])

    def _add_user_dlg(self):
        dlg = tk.Toplevel(self.app); dlg.title("Ajouter utilisateur"); dlg.grab_set()
        dlg.configure(bg=PAL["bg"]); dlg.geometry("400x360")
        tk.Frame(dlg, bg=PAL["btn_gray"], height=4).pack(fill="x")
        tk.Label(dlg, text="👤  Nouvel utilisateur", font=("Segoe UI",11,"bold"),
                 fg=PAL["text"], bg=PAL["bg"], padx=20, pady=12).pack(anchor="w")
        body = tk.Frame(dlg, bg=PAL["bg"], padx=24); body.pack(fill="x")
        vs = {k: tk.StringVar() for k in ["prenom","nom","email","tel","pwd","role"]}
        vs["role"].set("user")
        for lbl, key in [("Prénom *","prenom"),("Nom *","nom"),("Email *","email"),
                          ("Téléphone","tel"),("Mot de passe *","pwd")]:
            entry_row(body, lbl, vs[key], PAL["bg"], is_pwd=(key=="pwd"))
        combo_row(body, "Rôle", vs["role"], ["user","admin"], PAL["bg"])
        err = tk.Label(body, text="", font=("Segoe UI",8), fg=PAL["btn_red"], bg=PAL["bg"])
        err.pack(anchor="w", pady=(8,0))
        def _save():
            if not vs["email"].get() or not vs["pwd"].get():
                err.config(text="Email et mot de passe obligatoires."); return
            ok, msg = self.db.reg(vs["nom"].get(), vs["prenom"].get(), vs["email"].get(),
                                   vs["tel"].get(), vs["pwd"].get(), vs["role"].get())
            if not ok: err.config(text=msg); return
            dlg.destroy(); self._show_tab("users")
        bf = tk.Frame(dlg, bg=PAL["bg"], padx=24, pady=12); bf.pack(fill="x")
        pill_btn(bf, "Enregistrer", _save, bg=PAL["btn_connect"], pady=8).pack(side="right")
        pill_btn(bf, "Annuler", dlg.destroy, bg=PAL["btn_gray"], pady=8).pack(side="right", padx=(0,8))

    def _del_user(self, uid):
        if messagebox.askyesno("Supprimer","Supprimer cet utilisateur ?"):
            self.db.del_user(uid); self._show_tab("users")


# ══════════════════════════════════════════════════════════════════════════════
#  ALERT ENGINE
# ══════════════════════════════════════════════════════════════════════════════
class AlertEngine:
    CRITICAL = {"Fievre","Hypothermie"}; WARN = {"Elevee","En chaleur"}; COOLDOWN = 600

    def __init__(self, db, get_uid):
        self.db = db; self.get_uid = get_uid
        self._last = {}; self._callbacks = []

    def register(self, cb): self._callbacks.append(cb)

    def check(self, rfid, tc, statut, info):
        if statut not in self.CRITICAL and statut not in self.WARN: return
        now = datetime.now()
        last = self._last.get(rfid)
        if last and (now-last).total_seconds() < self.COOLDOWN: return
        self._last[rfid] = now
        nom = info.get("nom",rfid); uid = self.get_uid(); sid = info.get("site_id",0)
        icon = "🔴" if statut in self.CRITICAL else "🟠"
        msg  = f"{icon} {nom} ({rfid}) — {statut} : {tc:.1f}°C"
        type_ = "error" if statut in self.CRITICAL else "warning"
        if uid: self.db.add_notif(uid, msg, type_, rfid, sid)
        threading.Thread(target=self._beep, args=(statut,), daemon=True).start()
        for cb in self._callbacks:
            try: cb({"rfid":rfid,"msg":msg,"statut":statut,"tc":tc,"ts":now})
            except: pass
        # Email
        if uid:
            ec = self.db.get_email_cfg(uid)
            if ec.get("enabled") and ec.get("user"):
                threading.Thread(target=self._email, args=(ec,nom,rfid,tc,statut), daemon=True).start()

    @staticmethod
    def _beep(statut):
        if not WINSOUND_OK: return
        try:
            if statut=="Fievre":
                for _ in range(4): winsound.Beep(1400,200); __import__("time").sleep(0.08)
            elif statut=="Hypothermie":
                for _ in range(3): winsound.Beep(500,300); __import__("time").sleep(0.1)
            else: winsound.Beep(800,300)
        except: pass

    @staticmethod
    def _email(cfg, nom, rfid, tc, statut):
        try:
            msg = MIMEMultipart(); msg["From"]=cfg["user"]; msg["To"]=cfg["dest"]
            msg["Subject"] = f"[BovTemp] ⚠ {statut} — {nom}"
            body = f"Animal : {nom}\nRFID : {rfid}\nTemp. : {tc:.2f}°C\nStatut : {statut}\nHeure : {datetime.now():%d/%m/%Y %H:%M:%S}\n"
            msg.attach(MIMEText(body,"plain","utf-8"))
            with smtplib.SMTP(cfg["smtp"],int(cfg["port"])) as s:
                s.starttls(); s.login(cfg["user"],cfg["password"]); s.send_message(msg)
        except Exception as e: print(f"[Email] {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.db = DB(); self.user = None
        self.serial_mgr = SerialManager()
        self.alert_engine = AlertEngine(self.db, lambda: self.user["id"] if self.user else None)
        self._live_cbs = []; self._page = None
        self._current_site = None

        self.title("BovTemp v5")
        self.geometry("1280x820"); self.minsize(960,660)
        self.configure(bg=PAL["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._setup_styles()
        self._content = tk.Frame(self, bg=PAL["bg"]); self._content.pack(fill="both", expand=True)
        self._poll_serial()
        self.goto("login")

    def _setup_styles(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("TCombobox", fieldbackground=PAL["bg_input"], background=PAL["bg_input"],
                    foreground=PAL["text"], bordercolor=PAL["border"], arrowcolor=PAL["text_sub"], padding=3)
        s.configure("Vertical.TScrollbar", background=PAL["border"], troughcolor=PAL["bg"],
                    bordercolor=PAL["bg"], arrowcolor=PAL["text_sub"])
        s.configure("Treeview", background=PAL["bg_card"], foreground=PAL["text"],
                    fieldbackground=PAL["bg_card"], rowheight=26, font=("Segoe UI",8))
        s.configure("Treeview.Heading", background=PAL["bg_sect"], foreground=PAL["text_sub"],
                    font=("Segoe UI",7,"bold"), relief="flat", padding=(6,5))
        s.map("Treeview", background=[("selected","#D0E8FF")], foreground=[("selected",PAL["text"])])

    def goto(self, page, **kw):
        if self._page:
            try: self._page.destroy()
            except: pass
        for w in self._content.winfo_children(): w.destroy()
        self.configure(bg=PAL["bg"]); self._content.configure(bg=PAL["bg"])
        page_map = {
            "login":             (LoginPage,            {}),
            "register":          (RegisterPage,         {}),
            "accueil":           (AccueilPage,          {}),
            "betail":            (BetailPage,           {}),
            "detail_animal":     (DetailAnimalPage,     {"animal_id": kw.get("animal_id")}),
            "edit_animal":       (EditAnimalPage,       {"animal_id": kw.get("animal_id"), "site_id": kw.get("site_id")}),
            "detail_traitement": (DetailTraitementPage, {"rfid": kw.get("rfid"), "site_id": kw.get("site_id")}),
            "detail_vaccin":     (DetailVaccinPage,     {"rfid": kw.get("rfid"), "site_id": kw.get("site_id")}),
            "detail_alim":       (DetailAlimPage,       {"rfid": kw.get("rfid"), "site_id": kw.get("site_id")}),
            "traitements":       (TraitementsPage,      {}),
            "vaccins":           (VaccinsPage,          {}),
            "grossesse":         (GrossessePage,        {}),
            "alimentation":      (AlimentationPage,     {}),
            "stats":             (StatsPage,            {}),
            "backoffice":        (BackOfficePage,       {}),
        }
        PageClass, extra = page_map.get(page, (LoginPage, {}))
        self._page = PageClass(self._content, self, **extra)
        self._page.pack(fill="both", expand=True)

    def _logout(self):
        self.serial_mgr.stop(); self.user = None; self._live_cbs = []; self._current_site = None
        self.goto("login")

    def _on_close(self):
        self.serial_mgr.stop(); self.destroy()

    def start_serial(self, port, baudrate=9600):
        self.serial_mgr.start(port, baudrate)

    def stop_serial(self):
        self.serial_mgr.stop()

    def _poll_serial(self):
        while not self.serial_mgr.queue.empty():
            try:
                rfid, tf = self.serial_mgr.queue.get_nowait()
                self._dispatch_reading(rfid, tf)
            except: break
        self.after(100, self._poll_serial)

    def _dispatch_reading(self, rfid, tf):
        animal = self.db.get_animal(rfid=rfid)
        if animal is None:
            if self.user and self._current_site:
                aid = self.db.add_animal(self._current_site["id"], rfid, f"Animal {rfid}",
                                          "bovin", "Autre", "", "F", "", acquisition=1)
                animal = self.db.get_animal(aid=aid)
            else: return
        if not animal.get("acquisition",0): return
        info = {"site_id":animal["site_id"],"sexe":animal["sexe"],"nom":animal.get("nom",rfid)}
        tc = f2c(tf); statut = get_status(tc, info["sexe"]); sid = info["site_id"]
        self.db.add_temp(rfid, sid, tc, tf, statut)
        if statut in ("Fievre","Instable","Elevee"):
            self.db.upd_animal(animal["id"], statut_etat="instable")
        self.alert_engine.check(rfid, tc, statut, info)
        for cb in list(self._live_cbs):
            try: cb(rfid, tc, tf, statut, info)
            except: pass
        print(f"[RFID] {rfid} → {tc:.2f}°C [{statut}]")

    def register_live_callback(self, cb):
        if cb not in self._live_cbs: self._live_cbs.append(cb)

    def unregister_live_callback(self, cb):
        if cb in self._live_cbs: self._live_cbs.remove(cb)


# ══════════════════════════════════════════════════════════════════════════════
#  DEMO DATA
# ══════════════════════════════════════════════════════════════════════════════
def inject_demo(db):
    ok, _ = db.reg("Dupont","Jean","demo@bovtemp.com","0612345678","demo123","admin")
    if not ok: print("Demo existe. Login: demo@bovtemp.com / demo123"); return
    u = db.login("demo@bovtemp.com","demo123")
    s1 = db.add_site(u["id"],"Ferme des Oliviers","Route des Collines","Montpellier","France",
                     ["bovin","ovin"],280)
    s2 = db.add_site(u["id"],"Haras du Midi","Chemin des Pins","Nîmes","France",["equin"],35)

    animals = [
        (s1,"0088610114","Marguerite","bovin","Vache laitière","Holstein","F","2019-03-12","2019-05-01",420,"Lot A",1),
        (s1,"0088610007","Tornado",  "bovin","Bovin viande",  "Charolaise","M","2022-06-20","2022-08-01",680,"Lot B",0),
        (s1,"0088610009","Belle",    "bovin","Vache laitière","Montbéliarde","F","2021-07-05","2021-09-01",490,"Lot A",1),
        (s1,"0088610020","Brebis 01","ovin", "Brebis laitière","Lacaune","F","2020-04-10","2020-06-01",75,"Parc 1",1),
        (s2,"EQ000001",  "Sultan",   "equin","Cheval de sport","Pur-sang","M","2017-04-22","2018-01-01",550,"Box 1",1),
        (s2,"EQ000002",  "Perle",    "equin","Jument","Frison","F","2019-08-11","2020-03-01",480,"Box 2",0),
    ]
    for (sid,rfid,nom,esp,scat,race,sexe,dob,darr,poids,enclos,acq) in animals:
        db.add_animal(sid,rfid,nom,esp,scat,race,sexe,dob,darr,poids,enclos,acquisition=acq)

    # Températures historiques
    base = {"0088610114":38.7,"0088610007":40.9,"0088610009":39.6,"0088610020":38.5,
            "EQ000001":37.8,"EQ000002":38.2}
    now = datetime.now()
    for i in range(72):
        ts = (now-timedelta(hours=71-i)).strftime("%Y-%m-%d %H:%M:%S")
        for rfid, bc in base.items():
            tc = bc+random.uniform(-0.35,0.45); tf = c2f(tc)
            a = db.get_animal(rfid=rfid)
            if a:
                stat = get_status(tc, a["sexe"])
                db.cx.execute("INSERT INTO temps(rfid,site_id,tc,tf,statut,ts) VALUES(?,?,?,?,?,?)",
                              (rfid, a["site_id"], round(tc,2), round(tf,1), stat, ts))
    db.cx.commit()

    # Mettre Tornado en instable
    a = db.get_animal(rfid="0088610007")
    if a: db.upd_animal(a["id"], statut_etat="instable")

    # Traitement
    db.add_traitement("0088610007", s1, "10/01/2025", "Antibiotique", "2x/jour", "7 jours", "Traitement préventif")

    # Vaccination
    db.add_vaccination("0088610114", s1, "15/03/2025", "IBR", "Dose unique", "—")
    db.add_vaccination("EQ000001", s2, "20/02/2025", "Grippe équine", "1x/an", "—")

    # Gestation
    db.add_gestation("0088610114", s1, "01/10/2024", "10/07/2025", "Veau de printemps attendu")
    db.add_gestation("EQ000002", s2, "15/07/2024", "20/06/2025")

    # Alimentation
    db.add_alimentation("0088610114", s1, datetime.now().strftime("%d/%m/%Y"), "Foin", 8.5, "kg")
    db.add_alimentation("0088610009", s1, datetime.now().strftime("%d/%m/%Y"), "Concentré", 3.0, "kg")

    db.add_notif(u["id"],"Bienvenue sur BovTemp v5 !","success")
    db.add_notif(u["id"],"0088610007 (Tornado) — Fièvre détectée : 40.9°C","error","0088610007",s1)

    print("✓ Demo injecté. Login: demo@bovtemp.com / demo123")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    db = DB()
    if "--demo" in sys.argv:
        if not db.email_exists("demo@bovtemp.com"): inject_demo(db)
        else: print("Demo existe. Login: demo@bovtemp.com / demo123")
    del db
    app = App()
    app.mainloop()