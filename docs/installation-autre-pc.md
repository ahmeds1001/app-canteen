# Installer l'application sur un autre PC (présentation)

Toutes les commandes se tapent dans **cmd** (pas PowerShell). Comptez 20 à 30 minutes la première fois.

## Ce qu'il faut apporter (clé USB)

- Le fichier **`.env`** du PC de développement (à la racine du dossier `app canteen`). Il contient les clés
  secrètes et le mot de passe des comptes de test : **il n'est jamais sur GitHub**, ne l'envoyez pas par email.
- Facultatif : le dossier **`backend\media`** (photos des plats).

## 1. Installer les outils (une seule fois)

```bash
winget install Git.Git Python.Python.3.12 OpenJS.NodeJS.LTS Google.PlatformTools
```

Fermez et rouvrez cmd ensuite.

## 2. Récupérer le code

```bash
cd %USERPROFILE%\Desktop
```
```bash
git clone https://github.com/ahmeds1001/app-canteen.git "app canteen"
```
```bash
cd "app canteen"
```

Si GitHub demande de se connecter : compte **ahmeds1001**.

Copiez ensuite le fichier **`.env`** de la clé USB dans ce dossier (et `media` dans `backend` si vous l'avez).

## 3. Installer le backend et préparer les données

```bash
cd backend
```
```bash
python -m venv .venv
```
```bash
.venv\Scripts\pip install -r requirements\dev.txt
```
```bash
.venv\Scripts\python.exe manage.py migrate
```
```bash
.venv\Scripts\python.exe manage.py demo_week
```

`demo_week` crée les comptes de test, les plats et la semaine du 9 au 14 novembre (voir
`docs/guide-test-semaine.md`), puis règle l'horloge sur mardi 10/11 20:30.

## 4. Installer le frontend

```bash
cd ..\frontend
```
```bash
npm install
```

## 5. Juste avant la présentation

Depuis le dossier `app canteen` :

1. **Remettre l'horloge au départ, avant de lancer le planificateur** (l'horloge de test avance avec le temps
   réel ; si le planificateur tourne pendant ce temps, il « vit » la semaine à votre place) :
   ```bash
   backend\.venv\Scripts\python.exe backend\manage.py dev_clock set 2026-11-10 20:30
   ```
2. Lancer l'application (3 fenêtres) :
   ```bash
   start "backend" cmd /k "cd backend && .venv\Scripts\python.exe manage.py runserver"
   ```
   ```bash
   start "scheduler" cmd /k "cd backend && .venv\Scripts\python.exe manage.py run_scheduler"
   ```
   ```bash
   start "frontend" cmd /k "cd frontend && npm run dev"
   ```
3. Ouvrir http://localhost:5173 et suivre `docs/guide-test-semaine.md`.

## Recommencer la démo depuis le début

Une fois l'horloge avancée, la semaine ne peut pas être rejouée (un repas servi reste servi). Sur le PC de
présentation, la base ne contient que des données de démonstration : pour repartir de zéro, fermez les 3 fenêtres,
puis depuis `backend` :

```bash
del db.sqlite3
```
```bash
.venv\Scripts\python.exe manage.py migrate
```
```bash
.venv\Scripts\python.exe manage.py demo_week
```

Ne faites jamais cela sur une base contenant de vraies données.

## Le téléphone (Pixel)

1. Brancher le Pixel en USB, ou sur le même Wi-Fi : Paramètres → Système → Options pour les développeurs →
   **Débogage sans fil** → « Associer l'appareil avec un code ».
2. Sur le PC :
   ```bash
   adb pair ADRESSE:PORT_ASSOCIATION
   ```
   (le code à 6 chiffres affiché sur le téléphone est demandé), puis :
   ```bash
   adb connect ADRESSE:PORT
   ```
   (l'adresse et le port affichés en haut de l'écran « Débogage sans fil »).
3. Rediriger le port de l'application vers le téléphone :
   ```bash
   adb reverse tcp:5173 tcp:5173
   ```
4. Sur le Pixel, ouvrir Chrome à l'adresse http://localhost:5173.

Si `adb` dit « more than one device », ajoutez `-s ADRESSE:PORT` après `adb`.

## En cas de problème

| Symptôme | Solution |
| --- | --- |
| « Mot de passe incorrect » | Le `.env` n'a pas été copié avant `demo_week` : copiez-le, supprimez `db.sqlite3`, relancez migrate et demo_week |
| « Trop de tentatives » à l'inscription | Fermez et relancez la fenêtre backend (le compteur est remis à zéro) |
| Les réservations de mercredi sont closes | L'horloge a avancé : `dev_clock set 2026-11-10 20:30` (ou recommencer la démo, voir plus haut) |
| Le téléphone affiche « page inaccessible » | Refaire `adb reverse tcp:5173 tcp:5173` (à refaire après chaque reconnexion) |
