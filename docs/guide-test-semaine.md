# Guide de test — semaine du 9 au 14 novembre 2026

Les données de test sont ajoutées par `python manage.py demo_week` (dossier `backend/`). La commande n'efface rien :
elle réutilise les comptes et les plats existants, ajoute ceux qui manquent, construit la semaine si elle n'existe
pas encore, puis règle l'horloge de test sur **mardi 10 novembre, 20:30**.

Tout ce qui précède cette heure a été « vécu » par l'application avec ses vraies règles : menus publiés, réservations
et annulations, verrouillage à minuit, finalisation, scans, absences (no-show), notifications et journal d'audit.

## Lancer l'application (3 terminaux)

```bash
cd backend; .\.venv\Scripts\python.exe manage.py runserver
cd backend; .\.venv\Scripts\python.exe manage.py run_scheduler
cd frontend; npm.cmd run dev
```

Puis ouvrir http://localhost:5173. Le bandeau orange « Horloge de test » affiche l'heure simulée.

## Comptes

Mot de passe de tous les comptes : la valeur `DEV_SEED_PASSWORD` du fichier `.env`.

| Rôle | Email | Pour tester |
| --- | --- | --- |
| Employé | `employee@ovagri.test` | Réserver, annuler, QR code, rappels |
| RH | `hr@ovagri.test` | Approuver avec matricule, refuser, suspendre |
| Chef | `chef@ovagri.test` | Bibliothèque de plats, planification, publication |
| Direction | `management@ovagri.test` | Finalisation |
| Scanner | `scanner@ovagri.test` | Scan des QR, recherche manuelle, paiement |
| Admin | `admin@ovagri.test` | Rôles, tout le reste |

Autres comptes : 20 employés (`mohamed.benali@…`, `fatma.trabelsi@…`, matricules EMP-2001 à EMP-2020) qui
réservent et mangent ; **Riadh Hamdi** suspendu ; **Sarra Bouzid** et **Omar Tlili** en attente RH, sans matricule.

## État de départ (mardi 10/11, 20:30)

| Jour | État | Réservations | À savoir |
| --- | --- | --- | --- |
| Lun 9 | Terminé | 18 servis, 1 absent | Finalisé automatiquement à 10:00 ; l'employé de test était absent |
| Mar 10 | Terminé | 15 servis, 4 absents | Finalisé par la Direction (23 assiettes) ; l'employé de test servi à 12:41 |
| **Mer 11** | **Ouvert jusqu'à minuit** | 18 | L'employé de test n'a **pas** réservé |
| Jeu 12 | Ouvert | 11 | L'employé de test a réservé |
| Ven 13 | Ouvert, **payant 3,500 TND** | 12 | Le paiement se fait en espèces à la cantine |
| Sam 14 | **Brouillon** du chef | — | À publier avant jeudi minuit |
| Lun 16 → | Rien | — | Le chef doit planifier la semaine suivante |

## Changer l'heure

Depuis `backend/` (le planificateur applique les changements tout de suite) :

```bash
.\.venv\Scripts\python.exe manage.py dev_clock set 2026-11-11 08:30
```

Avancez toujours dans l'ordre des étapes : revenir en arrière ne défait pas ce qui s'est passé (un menu verrouillé
reste verrouillé, un repas servi reste servi).

---

## Étape 1 — Mardi 10/11, 20:30 (heure de départ)

**Employé**
1. La cloche affiche « Réservez pour demain » (rappel de 20:00).
2. Réserver **mercredi** → le QR code apparaît dans « Mes réservations ».
3. Annuler **jeudi**, puis réserver à nouveau.
4. Réserver **vendredi** (prix affiché : 3.500 TND) → la réservation est « À payer ».

**RH** (Comptes)
1. Onglet « En attente » : Sarra Bouzid et Omar Tlili, « Matricule à saisir ».
2. Approuver Sarra avec `EMP-2001` → refusé (déjà utilisé). Puis `EMP-2101` → approuvé.
3. Refuser Omar avec un motif.
4. Onglet « Suspendus » : réactiver Riadh Hamdi.

**Chef**
1. « Plats » : 14 plats, avec catégories et allergènes ; ajouter un plat avec photo.
2. « Planning » : publier **samedi 14** (brouillon) ; composer et publier **lundi 16**.
3. Modifier les plats de **jeudi** → les employés qui ont réservé jeudi reçoivent « Menu modifié ».

**Admin** : changer le rôle d'un employé (Comptes → Rôle).

## Étape 2 — Mercredi 11/11, 08:30 : finalisation

`dev_clock set 2026-11-11 08:30`

- **Employé** : mercredi n'est plus annulable (réservations closes à minuit).
- **Direction** : la cloche affiche « Assiettes à confirmer ». Écran « Finalisation » : réservations + 10 % de
  marge → confirmer, ou saisir un autre nombre (jamais en dessous des réservations).
- **Chef** : notification « Nombre d'assiettes » après la confirmation.

## Étape 3 — Mercredi 11/11, 10:05 : après l'heure limite

`dev_clock set 2026-11-11 10:05`

- **Direction** : le nombre d'assiettes ne peut plus être changé. Si mercredi n'avait pas été confirmé, il a été
  finalisé automatiquement (réservations + 10 %).

## Étape 4 — Mercredi 11/11, 12:30 : le service

`dev_clock set 2026-11-11 12:30`

**Scanner** (sur le téléphone ou le PC, voir le guide de test principal pour le Pixel)
1. Scanner le QR de mercredi de l'employé de test → « Repas validé » (vert).
2. Le scanner une deuxième fois → « Repas déjà servi » (rouge).
3. Scanner le QR de **jeudi** → « Ce code n'est pas pour aujourd'hui ».
4. Recherche manuelle : taper « Ben Ali » → « Valider la présence » pour Mohamed Ben Ali.

## Étape 5 — Mercredi 11/11, 15:05 : absences

`dev_clock set 2026-11-11 15:05`

- Les réservations non scannées de mercredi passent en « Absent » (visible dans « Mes réservations » d'un employé
  qui n'est pas venu, et dans la cloche).
- Les écrans « Rapports » sont prévus au sprint 2 : l'historique de lundi à mercredi (servis, absents, marge) est
  déjà dans la base pour les tester quand ils seront construits.

## Étape 6 — Vendredi 13/11, 12:30 : jour payant

`dev_clock set 2026-11-13 12:30`

Jeudi et vendredi sont finalisés automatiquement en passant 10:00 (si vous ne l'avez pas fait).

- **Scanner** : scanner le QR de vendredi de l'employé de test → « À payer 3,500 TND » → « Marquer payé ».
  Un deuxième appui ne compte pas un deuxième paiement.

## Fin des tests

```bash
.\.venv\Scripts\python.exe manage.py dev_clock reset
```

L'horloge revient à l'heure réelle ; les données restent.
