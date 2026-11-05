# Test de charge — Cantine OVAGRI

À faire **avant le lancement**, sur le serveur de l'entreprise, contre une **base de test séparée** : la base réelle
ne doit jamais recevoir les 200 comptes de test (rien n'est supprimé, par décision de l'entreprise).

Deux scénarios (`locustfile.py`) :

| Scénario | Ce qu'il simule | Limite (95 % des requêtes) |
| --- | --- | --- |
| `LoginRush` | Jour du lancement : chaque compte se connecte une fois, tous dans la même minute | connexion < 5 s |
| `ReservationRush` | Les dernières minutes avant la clôture : connexion, menus, réserver, changer de menu, annuler, solde | < 1 s pour tout sauf la connexion |

Le test échoue (code de sortie 1) si plus de 1 % des requêtes échouent ou si une limite est dépassée. La ligne
`VERDICT` résume le résultat par type de requête.

## 1. Préparer une installation de test

Sur le serveur, à côté de l'installation réelle (ou avant elle) :

1. Créer une base **`canteen_loadtest`** (même script que la base réelle, autre nom).
2. Copier `.env` en `.env.loadtest` et y changer :
   ```bash
   DB_NAME=canteen_loadtest
   THROTTLE_LOGIN=10000/min
   LOADTEST_PASSWORD=<un mot de passe de test>
   ```
   `THROTTLE_LOGIN` lève la limite de 10 connexions par minute : pendant le test, toutes les requêtes viennent de
   la même machine. **Ne jamais le mettre dans le `.env` réel.**
3. Démarrer cette installation à côté de la vraie : autre nom de projet, autre fichier de réglages, autre port
   (8081 ; à relayer par le proxy sur une adresse de test, ou à viser directement depuis le réseau interne) :
   ```bash
   export ENV_FILE=.env.loadtest WEB_PORT=8081
   docker compose -p cantine-loadtest up -d --build
   docker compose -p cantine-loadtest run --rm backend python manage.py loadtest_accounts --count 200
   ```
   La commande crée `user001…user200@loadtest.ovagri.test` avec 100 TND chacun et publie le premier jour encore
   ouvert, avec deux menus. Elle refuse de tourner si le nom de la base ne contient pas « loadtest ».

## 2. Lancer les scénarios

Depuis un poste avec Python 3.12 :

```bash
pip install -r loadtest/requirements.txt
```

```bash
set LOADTEST_PASSWORD=<le mot de passe de test>
```

Jour du lancement — 200 connexions en une minute :

```bash
locust -f loadtest/locustfile.py LoginRush --headless -u 200 -r 4 -t 90s --host https://<adresse de test> --csv loadtest/login
```

Rush du soir — 200 personnes pendant 5 minutes :

```bash
locust -f loadtest/locustfile.py ReservationRush --headless -u 200 -r 10 -t 5m --host https://<adresse de test> --csv loadtest/rush
```

Sans `--headless`, Locust ouvre une page http://localhost:8089 avec les courbes en direct.

Pendant le test, regarder sur le serveur : `docker stats` (mémoire et CPU du backend, limite 2 Go / 2 CPU) et
`docker compose -p cantine-loadtest logs backend` (erreurs).

## 3. Lire le résultat

- **OK** : garder les réglages (`GUNICORN_WORKERS=4`, `GUNICORN_THREADS=2`, serveur 4 vCPU / 4 Go).
- **Connexions trop lentes** : le serveur manque de CPU (la vérification Argon2 du mot de passe est volontairement
  coûteuse) → plus de vCPU, ou étaler le lancement par service.
- **Autres requêtes lentes ou en erreur** : regarder les journaux du backend et la charge de SQL Server ;
  augmenter `GUNICORN_WORKERS` (et la limite mémoire du backend dans `docker-compose.yml`).

Après le test : `ENV_FILE=.env.loadtest docker compose -p cantine-loadtest down` (la base `canteen_loadtest` peut être gardée pour un
prochain test).

## Essai à blanc du 5 novembre 2026

Sur le poste de développement (serveur de développement Django, un seul processus, SQL Server Express), 60 comptes :
60 connexions simultanées sans erreur ; rush de 60 personnes pendant 45 s, 1 027 requêtes sans erreur, 95 % des
réservations en moins de 63 ms. Ces chiffres valident le kit, pas le serveur : le vrai test se fait sur le serveur
de l'entreprise.
