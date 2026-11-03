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
| Direction | `management@ovagri.test` | Finalisation par menu, prix du jour, caisse et corrections, liste du jour |
| Scanner | `scanner@ovagri.test` | Scan des QR (menu à servir), recherche manuelle, caisse (recharges), liste du jour |
| Admin | `admin@ovagri.test` | Rôles, tout le reste |

Autres comptes : 20 employés (`mohamed.benali@…`, `fatma.trabelsi@…`, matricules EMP-2001 à EMP-2020) qui
réservent et mangent ; **Riadh Hamdi** suspendu ; **Sarra Bouzid** et **Omar Tlili** en attente RH, sans matricule.

## État de départ (mardi 10/11, 20:30)

Chaque repas est payé avec le **solde prépayé** de l'employé au moment de la réservation : 3,000 TND, sauf
vendredi 3,500 TND. Tous les employés ont rechargé 20 à 50 TND ; l'**employé de test** a rechargé 15 TND et a payé
lundi, mardi et jeudi : **il lui reste 6 TND**.

| Jour | Menus | État | À savoir |
| --- | --- | --- | --- |
| Lun 9 | 1 menu | Terminé | Finalisé automatiquement à 10:00 ; l'employé de test était absent (repas payé quand même) |
| Mar 10 | 2 menus | Terminé | Finalisé par la Direction, par menu ; l'employé de test (menu 2) servi à 12:41 |
| **Mer 11** | **2 menus** | **Ouvert jusqu'à minuit** | L'employé de test n'a **pas** réservé |
| Jeu 12 | 2 menus | Ouvert | L'employé de test a réservé le menu 1 |
| Ven 13 | 2 menus | Ouvert, **3,500 TND** | L'employé de test n'aura pas assez de solde |
| Sam 14 | 1 menu | **Brouillon** du chef | À publier avant jeudi minuit |
| Lun 16 → | — | Rien | Le chef doit planifier la semaine suivante |

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
1. La cloche affiche « Réservez pour demain » (rappel de 20:00). En haut à droite : « Solde : 6.000 TND ».
2. **Mercredi** : « Réserver le menu 2 » → le solde passe à 3.000 TND, le QR code apparaît dans « Mes réservations »
   avec « Menu 2 ».
3. **Jeudi** : « Prendre ce menu à la place » sur le menu 2 → le choix change, le solde ne bouge pas.
4. **Jeudi** : « Annuler (remboursé : 3.000 TND) » → message de remboursement, solde 6.000 TND. Réserver de nouveau.
5. **Vendredi** (3.500 TND) : « Solde insuffisant » → les boutons sont désactivés.
6. « Mon solde » : l'historique (recharge, repas, remboursement), avec le solde après chaque mouvement.

**Scanner** (Caisse)
1. « Caisse » : rechercher « employe » → ouvrir le compte de l'employé de test.
2. Choisir « 10 TND » → « Enregistrer 10.000 TND » → confirmer → nouveau solde 13.000 TND (l'employé reçoit une
   notification « Solde rechargé »).
3. Retour employé : réserver **vendredi** → le solde passe à 9.500 TND.
4. « Liste du jour » : les réservations de mardi (menu, statut, heure de service), puis jour suivant ; filtres,
   recherche « Ben Ali », « Exporter (CSV) ».

**Direction**
1. « Caisse » : sur un compte, « Corriger le solde » (ex. -5, motif « Erreur de saisie ») → l'historique garde les deux
   mouvements. Le scanner n'a pas ce bouton.
2. « Finalisation » : réservations par menu ; « Prix du jour » de samedi modifiable (jusqu'à vendredi minuit).
3. « Liste du jour » : comme le scanner.

**RH** (Comptes)
1. Onglet « En attente » : Sarra Bouzid et Omar Tlili, « Matricule à saisir ».
2. Approuver Sarra avec `EMP-2001` → refusé (déjà utilisé). Puis `EMP-2101` → approuvé.
3. Refuser Omar avec un motif.
4. Onglet « Suspendus » : réactiver Riadh Hamdi.

**Chef**
1. « Plats » : 17 plats, avec catégories et allergènes ; ajouter un plat avec photo.
2. « Planning » : **samedi 14** → « Modifier les plats » → onglet « Menu 2 » : ajouter un deuxième menu, puis
   « Publier ». Composer et publier **lundi 16**.
3. Modifier les plats de **jeudi** → les employés qui ont réservé jeudi reçoivent « Menu modifié ».
4. Essayer d'enlever le menu 2 de **jeudi** → refusé : des employés l'ont réservé.

**Admin** : changer le rôle d'un employé (Comptes → Rôle).

## Étape 2 — Mercredi 11/11, 08:30 : finalisation

`dev_clock set 2026-11-11 08:30`

- **Employé** : mercredi n'est plus annulable (réservations closes à minuit).
- **Direction** : la cloche affiche « Assiettes à confirmer ». Écran « Finalisation » : un nombre par menu
  (réservations + 10 % de marge chacun) → confirmer, ou saisir d'autres nombres (jamais en dessous des
  réservations du menu).
- **Chef** : notification « Nombre d'assiettes » avec le détail par menu, après la confirmation.

## Étape 3 — Mercredi 11/11, 10:05 : après l'heure limite

`dev_clock set 2026-11-11 10:05`

- **Direction** : le nombre d'assiettes ne peut plus être changé. Si mercredi n'avait pas été confirmé, il a été
  finalisé automatiquement (réservations + 10 %).

## Étape 4 — Mercredi 11/11, 12:30 : le service

`dev_clock set 2026-11-11 12:30`

**Scanner** (sur le téléphone ou le PC, voir le guide de test principal pour le Pixel)
1. Scanner le QR de mercredi de l'employé de test → « Repas validé » (vert), avec **« Menu 2 »** en gros et ses
   plats : c'est l'assiette à servir. Badge « Payé par le solde ».
2. Le scanner une deuxième fois → « Repas déjà servi » (rouge).
3. Scanner le QR de **jeudi** → « Ce code n'est pas pour aujourd'hui ».
4. Recherche manuelle : taper « Ben Ali » → « Valider la présence » pour Mohamed Ben Ali.

## Étape 5 — Mercredi 11/11, 15:05 : absences

`dev_clock set 2026-11-11 15:05`

- Les réservations non scannées de mercredi passent en « Absent » (visible dans « Mes réservations » d'un employé
  qui n'est pas venu, et dans « Liste du jour »). Le repas reste payé : pas de remboursement.
- Les écrans « Rapports » sont prévus au sprint 2 : l'historique de lundi à mercredi (servis, absents, marge) est
  déjà dans la base pour les tester quand ils seront construits.

## Étape 6 — Vendredi 13/11, 12:30 : le prix du jour

`dev_clock set 2026-11-13 12:30`

Jeudi et vendredi sont finalisés automatiquement en passant 10:00 (si vous ne l'avez pas fait).

- **Scanner** : scanner le QR de vendredi de l'employé de test → « Payé par le solde (3.500 TND) ». Rien à encaisser
  à la cantine : il n'y a plus de paiement au comptoir, tout passe par le solde.

## Fin des tests

```bash
.\.venv\Scripts\python.exe manage.py dev_clock reset
```

L'horloge revient à l'heure réelle ; les données restent.
