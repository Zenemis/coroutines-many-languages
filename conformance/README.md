# Tests de conformité (indépendants du langage)

Ces tests vérifient qu'une implémentation, quel que soit son langage, se comporte comme une coroutine au sens de **`std::ops::Coroutine` de Rust**, qui sert de sémantique de référence. Ils complètent les tests de chaque langage, sans les remplacer.

## Deux niveaux de test

| Niveau | Oracle | Ce qu'il attrape | Où |
|---|---|---|---|
| **Conformité** (indépendant du langage) | Les lignes `<` des scénarios, c'est-à-dire la spécification écrite une fois | Les écarts de sémantique : démarrage paresseux, panic après la fin, première valeur de reprise, libération à l'abandon… | Ici |
| **Différentiel** (dans un langage) | Une seconde version des mêmes corps, écrite avec la lib standard du langage | Les bugs de mécanique qu'une traduction de corps pourrait masquer | Dans chaque implémentation |

**Limite connue de la conformité.** Le corps et l'adaptateur sont réécrits dans chaque langage, et rien ne vérifie automatiquement que cette traduction est fidèle à [`CATALOGUE.md`](CATALOGUE.md). C'est pour ça que les corps doivent rester triviaux, et que le niveau différentiel existe. Aucun de ces deux niveaux n'empêche de tricher : ils protègent contre les erreurs, pas contre la mauvaise foi.

## Comment ça marche

L'API d'une coroutine ne peut pas être la même dans tous les langages. On ne teste donc pas le code directement, mais un **petit programme**, l'adaptateur, que chaque langage fournit. Il :

1. contient le **catalogue** des corps, écrits avec l'implémentation testée ;
2. lit des **commandes** sur stdin (`new`, `resume`, `drop`) ;
3. écrit **une ligne par événement** sur stdout (`yield`, `return`, `print`, `panic`, `error`).

```
scénario .scn  ──commandes >──▶  adaptateur (Rust, C, Kotlin…)  ──événements──▶  lanceur : diff avec les lignes <
```

Le détail est dans [`PROTOCOLE.md`](PROTOCOLE.md).

Pour voir le fonctionnement à la main, sans le lanceur :

```bash
printf 'new feu 1 as f\nresume f\nresume f\n' | python3 conformance/reference/adapter.py
```

## L'adaptateur de référence

[`reference/adapter.py`](reference/adapter.py) utilise les générateurs natifs de Python, pliés à la sémantique de `std::ops::Coroutine`. Les générateurs sont éprouvés, donc **si un scénario échoue contre la référence, c'est le scénario qui est faux**.

À chaque ajout d'un corps dans `CATALOGUE.md`, il faut aussi l'ajouter à la référence.

## Organisation

- `scenarios/a1/`, `scenarios/a2/` : un fichier `.scn` par comportement, rangés par fonctionnalité.
- [`CATALOGUE.md`](CATALOGUE.md) : les corps communs, décrits en langage naturel et en pseudo-code.
- [`PROTOCOLE.md`](PROTOCOLE.md) : les commandes, les événements, la sémantique attendue et la déclaration des adaptateurs.
- `reference/` : l'adaptateur de référence en Python.
- `runner/` : le lanceur commun (`run.py`, Python ≥ 3.10, sans dépendance) et ses auto-tests.
- `adapters.json` : la liste des adaptateurs à lancer.
- L'adaptateur de chaque langage vit à côté de son implémentation, par exemple dans `rust/A-machine-a-etats/`.

## Lancer

```bash
python3 conformance/runner/run.py -v
```

## Reste à faire

- A3 (symétrique) : définir comment une coroutine passe la main à une autre dans le protocole.
