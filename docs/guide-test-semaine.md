# Guide de test — semaine du 30 novembre au 5 décembre 2026

Les données de test sont ajoutées par `python manage.py demo_week` (dossier `backend/`). La commande n'efface rien :
elle réutilise les comptes et les plats existants, ajoute ceux qui manquent, construit la semaine si elle n'existe
pas encore, remet le solde de l'employé de test à 15 TND avant la semaine, ajoute deux inscriptions en attente, puis
règle l'horloge de test sur **mardi 1er décembre, 20:30**.

Tout ce qui précède cette heure a été « vécu » par l'application avec ses vraies règles : menus publiés, réservations
et annulations, clôture à minuit, finalisation, scans, absences (no-show), notifications et journal d'audit. Chaque
résultat attendu ci-dessous a été vérifié en rejouant le guide sur une copie de la base (5 novembre 2026).

## Préparer la semaine de test (une seule fois)

```bash
backend\.venv\Scripts\python.exe backend\manage.py demo_week
```

Si la semaine existe déjà, la commande ne change rien et remet seulement l'horloge.

**Paramètres par défaut.** Le guide suppose les valeurs d'origine de l'écran « Paramètres » : réservations jusqu'à
23:59 la veille, finalisation à 10:00, service de 12:00 à 15:00, rappel du soir à **20:00**, marge de 10 %.

## Lancer l'application (3 fenêtres cmd)

```bash
start "backend" cmd /k "cd backend && .venv\Scripts\python.exe manage.py runserver"
start "scheduler" cmd /k "cd backend && .venv\Scripts\python.exe manage.py run_scheduler"
start "frontend" cmd /k "cd frontend && npm run dev"
```

Puis ouvrir http://localhost:5173. Le bandeau orange « Horloge de test » affiche l'heure simulée. La cloche peut
contenir des notifications des semaines précédentes : commencer par « Tout marquer comme lu » sur chaque compte.

## Comptes

Mot de passe de tous les comptes : la valeur `DEV_SEED_PASSWORD` du fichier `.env`.

| Rôle | Email | Pour tester |
| --- | --- | --- |
| Employé | `employee@ovagri.test` | Réserver, changer de menu, annuler, QR code, solde |
| RH | `hr@ovagri.test` | Approuver avec matricule, refuser, réactiver |
| Chef | `chef@ovagri.test` | Bibliothèque de plats, planning, publication |
| Direction | `management@ovagri.test` | Finalisation par menu, prix du jour, corrections, encaissements, liste du jour, rapports |
| Scanner | `scanner@ovagri.test` | Scan des QR (menu à servir), recherche manuelle, liste du jour — **pas d'argent** |
| Caissier | `cashier@ovagri.test` | Caisse (recharges), encaissements du jour et feuille de remise — **pas de scan** |
| Admin | `admin@ovagri.test` | Rôles, **Paramètres** (délais et horaires), tout le reste |

Autres comptes : 20 employés (`mohamed.benali@…`, `hichem.gharbi@…`, matricules EMP-2001 à EMP-2020) qui réservent
et mangent ; **Riadh Hamdi** suspendu ; **Sarra Bouzid** et **Omar Tlili** en attente RH, sans matricule.

## État de départ (mardi 1/12, 20:30)

Chaque repas est payé avec le **solde prépayé** au moment de la réservation : 3,000 TND, vendredi 3,500 TND.
L'**employé de test** avait 15 TND avant la semaine et a payé lundi, mardi et jeudi : **il lui reste 6,000 TND**.

| Jour | Menus | État | Employé de test |
| --- | --- | --- | --- |
| Lun 30/11 | 1 | Terminé | Menu 1 réservé, **absent** (repas payé quand même) |
| Mar 1/12 | 2 | Terminé | Menu 2, **servi** à 12:41 |
| **Mer 2/12** | **2** | **Ouvert jusqu'à minuit** | **Pas** réservé |
| Jeu 3/12 | 2 | Ouvert | Menu 1 réservé |
| Ven 4/12 | 2 | Ouvert, **3,500 TND** | Pas réservé (solde trop juste) |
| Sam 5/12 | 1 | **Brouillon** du chef | À publier avant jeudi 3/12 minuit |
| Lun 7/12 → | — | Rien | Le chef doit planifier la semaine suivante |

## Changer l'heure

Chaque étape commence par sa commande (depuis le dossier de l'application), puis rafraîchir la page. Avancez toujours
dans l'ordre des étapes : revenir en arrière ne défait pas ce qui s'est passé (un menu clôturé reste clôturé, un repas
servi reste servi).

---

## Étape 1 — Mardi 1/12, 20:30 (heure de départ)

```bash
backend\.venv\Scripts\python.exe backend\manage.py dev_clock set 2026-12-01 20:30
```

**Employé**
1. La cloche affiche « Pensez à réserver » pour mercredi 2 décembre. En haut : « Solde : 6.000 TND ». Chaque jour
   ouvert indique « Réservations jusqu'au … ».
2. **Mercredi** : « Réserver le menu 2 » → solde **3.000** ; le rappel passe en « Déjà traité » ; le QR code apparaît
   dans « Mes réservations » avec « Menu 2 ».
3. **Jeudi** : « Prendre ce menu à la place » (menu 2) → le choix change, le solde reste 3.000.
4. **Jeudi** : « Annuler (remboursé : 3.000 TND) » → solde **6.000**. Réserver de nouveau le menu 1 → solde **3.000**.
5. **Vendredi** (3.500 TND) : « Solde insuffisant », boutons désactivés.
6. « Mon solde » : l'historique avec le solde après chaque mouvement (dont « Solde remis à 15 TND » avant la semaine).

**Caissier** (Caisse et encaissements)
1. « Caisse » : rechercher « employe » → « 10 TND » → « Enregistrer » → confirmer → solde **13.000** (notification
   « Solde rechargé »).
2. Retour employé : réserver **vendredi** → solde **9.500**.
3. « Encaissements » (« Mon encaissement du jour ») : 1 recharge, « Argent à remettre » **10.000 TND**. « Imprimer » →
   la feuille de remise (chaque recharge, total, montant compté, deux signatures).
4. Le caissier n'a ni « Scanner » ni « Liste du jour ».

**Scanner**
1. « Liste du jour » : les réservations de mardi (menu, statut, heure de service), puis mercredi ; filtres, recherche,
   « Exporter (CSV) ».
2. Le scanner n'a ni « Caisse » ni « Encaissements » (ouvrir `/cashier` ramène aux menus).

**Direction**
1. « Caisse » : ouvrir **Mohamed Ben Ali** → « Corriger le solde » : -5, motif « Erreur de saisie ». Le caissier n'a pas
   ce bouton.
2. « Encaissements » de mardi 1/12 : par personne « Caisse Test 10.000 » (la même somme que la feuille du caissier),
   la correction de -5.000 avec son motif, **total encaissé 5.000 TND**.
3. « Finalisation » : réservations par menu ; « Prix du jour » de samedi modifiable.
4. « Rapports » : présence par employé du mois (Réservés = Servis + Absences + Pas encore servis) ; cliquer un employé
   pour voir ses jours.

**RH** (Comptes)
1. Onglet « En attente » : Sarra Bouzid et Omar Tlili, « Matricule à saisir ».
2. Approuver Sarra avec `EMP-2001` → refusé (déjà utilisé). Puis `EMP-3011` → approuvé : sa notification passe en
   « Déjà traité » pour tous les RH.
3. Refuser Omar avec un motif.
4. Onglet « Suspendus » : réactiver Riadh Hamdi.

**Chef**
1. « Plats » : la bibliothèque (17 plats sur une base neuve) ; ajouter un plat avec photo.
2. « Planning » : **samedi 5/12** → « Modifier les plats » → onglet « Menu 2 » → « Publier ». Semaine suivante :
   composer et publier **lundi 7/12**.
3. Enlever le menu 2 de **jeudi 3/12** → refusé : des employés l'ont réservé.

**Admin**
1. Changer le rôle d'un employé (Comptes → Rôle), par exemple en « Caissier ».
2. « Paramètres » : passer le rappel des employés à 19:30 → « Enregistrer » ; la page « Notifications » affiche
   « À 19:30, si vous n'avez pas encore réservé… ».
3. Clôture des réservations à 0 jour, 11:00 → refusé (« La clôture des réservations doit précéder l'heure de
   finalisation »).
4. **Remettre le rappel à 20:00** avant l'étape 2 : la suite du guide suppose les horaires par défaut.

## Étape 2 — Mercredi 2/12, 08:30 : finalisation

```bash
backend\.venv\Scripts\python.exe backend\manage.py dev_clock set 2026-12-02 08:30
```

- **Employé** : mercredi n'est plus annulable (réservations clôturées à minuit).
- **Direction** : « Assiettes à confirmer ». Écran « Finalisation » : un nombre par menu, réservations + 10 % arrondi
  au-dessus (ex. 12 → 14, 6 → 7) → confirmer. Le rappel passe en « Déjà traité » pour toute la Direction.
- **Chef** : notification « Nombre d'assiettes » avec le détail par menu.

## Étape 3 — Mercredi 2/12, 10:05 : après l'heure limite

```bash
backend\.venv\Scripts\python.exe backend\manage.py dev_clock set 2026-12-02 10:05
```

- **Direction** : le nombre d'assiettes ne peut plus être changé. Si mercredi n'avait pas été confirmé, il a été
  finalisé automatiquement (réservations + 10 %).

## Étape 4 — Mercredi 2/12, 12:30 : le service

```bash
backend\.venv\Scripts\python.exe backend\manage.py dev_clock set 2026-12-02 12:30
```

**Scanner** (sur le téléphone ou le PC)
1. Scanner le QR de mercredi de l'employé de test → « Repas validé » (vert), **« Menu 2 »** en gros et ses plats :
   c'est l'assiette à servir. Badge « Payé par le solde ».
2. Le scanner une deuxième fois → « Repas déjà servi » (rouge).
3. Scanner le QR de **jeudi** → « Ce code n'est pas pour aujourd'hui ».
4. Recherche manuelle : taper « Gharbi » → « Valider la présence » pour Hichem Gharbi.

## Étape 5 — Mercredi 2/12, 15:05 : absences

```bash
backend\.venv\Scripts\python.exe backend\manage.py dev_clock set 2026-12-02 15:05
```

- Avant 15:00, « Liste du jour » affiche « Pas encore servi » ; après, les réservations non scannées de mercredi
  passent en « Absent ». Le repas reste payé : pas de remboursement.
- **Direction** : « Rapports » (décembre) → les absences de mercredi apparaissent ; le taux d'absence ne compte que
  les journées terminées.

## Étape 6 — Vendredi 4/12, 12:30 : le prix du jour

```bash
backend\.venv\Scripts\python.exe backend\manage.py dev_clock set 2026-12-04 12:30
```

Jeudi et vendredi ont été finalisés automatiquement à 10:00 ; jeudi est terminé.

- **Scanner** : scanner le QR de vendredi de l'employé de test → « Payé par le solde (3.500 TND) ». Rien à encaisser :
  tout passe par le solde.
- **Employé** : « Mon solde » → **9.500 TND**.

## Fin des tests

```bash
backend\.venv\Scripts\python.exe backend\manage.py dev_clock reset
```

L'horloge revient à l'heure réelle ; les données restent.

## Refaire les tests une autre fois

Une semaine de test ne sert qu'une fois. Pour recommencer, construire la semaine suivante :

```bash
backend\.venv\Scripts\python.exe backend\manage.py demo_week --monday 2026-12-07
```

Tout se passe de la même façon **sept jours plus tard** : ajouter 7 jours à chaque date des commandes
(`2026-12-08 20:30`, `2026-12-09 08:30`…) et prendre un autre matricule libre pour Sarra (ex. `EMP-3012`). Le solde de
départ (6.000 TND) et les deux inscriptions en attente sont remis à l'identique.
