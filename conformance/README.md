# Tests de conformité (indépendants du langage)

> **Statut : l'approche par adaptateur est adoptée.** Le protocole détaillé (proposition v0) est dans [`PROTOCOLE.md`](PROTOCOLE.md).

Ces tests vérifient qu'une implémentation, quel que soit son langage, se comporte comme une coroutine selon le sens défini ici. Ils complètent les tests unitaires de chaque langage, sans les remplacer.

## Le problème

L'API d'une coroutine ne peut pas être la même partout. En Rust ce sera un `enum` ou un trait, en C une `struct` avec des macros, en Kotlin autre chose encore. On ne peut donc pas écrire un seul test qui appelle directement le code de chaque langage, sauf à passer par une FFI, ce qui serait pénible et fragile.

## L'idée : un adaptateur à la frontière du processus

L'adaptateur n'est pas une couche de code, c'est un **petit programme**. Chaque langage fournit un exécutable qui :

1. contient un **catalogue de corps de coroutines** écrits dans ce langage, avec l'implémentation maison (par exemple `compteur`, `cuisinier`, `fibonacci`…) ;
2. lit des **commandes** sur son entrée standard (créer une instance, la reprendre, lui envoyer une valeur, l'abandonner) ;
3. écrit sur sa sortie standard **une ligne par événement** (valeur produite, valeur finale, erreur, effet de bord).

Un lanceur commun (en Python par exemple) envoie les commandes de chaque scénario et compare la sortie à celle attendue. Les scénarios sont écrits **une seule fois**, et pour chaque langage on ne réécrit que l'adaptateur.

```
scénario (.txt)  ──commandes──▶  adaptateur Rust / C / Kotlin…  ──événements──▶  lanceur : diff avec l'attendu
```

## Format envisagé d'un scénario

Un fichier texte en trois parties : une description en langage naturel (la spécification), les commandes envoyées (`>`) et les lignes attendues (`<`).

```
# Titre du scénario
# Ce que ce test vérifie, et pourquoi c'est important, en français.

> new compteur 2 as c
> resume c
< yield 0
> resume c
< yield 1
> resume c
< return done
```

*(Exemple purement illustratif du format, pas un scénario retenu.)*

## Ce qui reste à décider

- Valider le vocabulaire proposé dans [`PROTOCOLE.md`](PROTOCOLE.md).
- La liste des corps du catalogue (`CATALOGUE.md`), qui doit être la même pour tous les langages.
- Comment exprimer les scénarios symétriques (A3), où une coroutine en reprend une autre.

## Organisation

- `scenarios/<fonctionnalité>/` : un fichier `.scn` par scénario, par exemple `scenarios/a1/`.
- `runner/` : le lanceur commun (`run.py`, Python ≥ 3.10, sans dépendance) et ses auto-tests.
- `adapters.json` : la liste des adaptateurs à lancer. Le format est décrit dans [`PROTOCOLE.md`](PROTOCOLE.md).
- L'adaptateur de chaque langage vit à côté de l'implémentation, par exemple `rust/A-machine-a-etats/`.
