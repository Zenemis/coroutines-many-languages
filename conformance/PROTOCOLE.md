# Protocole adaptateur ↔ lanceur — v0 (proposition)

> **Statut : proposition à valider.** Le protocole couvre A1 et A2. A3 (symétrique) est laissée pour plus tard.

## Principe

- Le lanceur démarre l'adaptateur, lui écrit **toutes** les commandes du scénario sur stdin, puis ferme stdin.
- L'adaptateur exécute les commandes dans l'ordre et écrit **une ligne par événement** sur stdout.
- Le lanceur compare la sortie complète, ligne par ligne, avec les lignes `<` attendues.
- Tout est déterministe : pas besoin d'aller-retour interactif.
- L'adaptateur termine avec le code de sortie 0, même si des erreurs `error …` ont été émises, puisque ces erreurs font partie du comportement testé. Un code différent de 0 (un `panic`, une segfault…) fait échouer le test.

## Lexique

- **Jeton** : une suite de caractères sans espace. Les valeurs sont des jetons, par exemple `0`, `-3` ou `bonjour`.
- **Nom** : l'identifiant d'une instance, choisi par le scénario (`c`, `a`, `b`…).
- **Corps** : le nom d'une coroutine du catalogue commun (voir `CATALOGUE.md`, à écrire).

## Commandes (stdin)

| Commande | Sens |
|---|---|
| `new <corps> [arg…] as <nom>` | Crée une instance du corps avec ses arguments, sans l'exécuter. |
| `resume <nom>` | Reprend l'instance sans lui envoyer de valeur (A1). |
| `resume <nom> <valeur>` | Reprend l'instance en lui envoyant une valeur (A2). |
| `drop <nom>` | Abandonne l'instance. Le nom n'est plus valide ensuite. |

Une commande ne produit une sortie que si **quelque chose se passe**. `new` et `drop` sont donc silencieuses, sauf si le corps a des effets (voir `print`).

## Événements (stdout)

| Événement | Sens |
|---|---|
| `yield <valeur>` | L'instance s'est suspendue en produisant une valeur. |
| `return [valeur]` | L'instance est terminée, avec ou sans valeur finale. |
| `print <texte…>` | Effet de bord du corps, par exemple « Cuisinier : je fais cuire ». Le texte va jusqu'à la fin de la ligne et peut contenir des espaces. |
| `error finished` | On a repris une instance déjà terminée. C'est **l'erreur dédiée**. |
| `error unknown <nom>` | Le nom ne correspond à aucune instance vivante : jamais créée, ou déjà abandonnée. Erreur du protocole, pas de la coroutine. |

Les `print` d'un corps apparaissent **avant** l'événement `yield` ou `return` de la même reprise, dans l'ordre où ils ont eu lieu.

## Format d'un fichier de scénario

```
# Titre
# Description en langage naturel : ce qui est vérifié, et pourquoi.

> commande
< événement attendu
```

- Les lignes `#` et les lignes vides sont ignorées par le lanceur.
- L'entrelacement des `>` et `<` sert seulement à la lecture. Le lanceur envoie toutes les `>` d'un coup et compare toutes les `<` d'un coup.
- Extension : `.scn`.

## Fonctionnalités

Les scénarios sont rangés par fonctionnalité : `scenarios/<fonctionnalité>/<nom>.scn`, par exemple `scenarios/a1/` et `scenarios/a2/`. Chaque adaptateur déclare les fonctionnalités qu'il supporte, et le lanceur ne lui envoie que les scénarios correspondants.

## Déclarer un adaptateur

Dans [`adapters.json`](adapters.json) :

```json
{
  "adapters": {
    "rust-A": {
      "cwd": "rust/A-machine-a-etats",
      "build": ["cargo", "build", "-q", "--bin", "adapter"],
      "command": ["target/debug/adapter"],
      "features": ["a1"],
      "timeout": 10
    }
  }
}
```

| Champ | Obligatoire | Sens |
|---|---|---|
| `cwd` | oui | Dossier de travail, relatif à la racine du dépôt. |
| `command` | oui | Commande qui lance l'adaptateur. Si l'exécutable contient un `/`, il est relatif à `cwd`. |
| `features` | oui | Sous-dossiers de `scenarios/` à lancer. |
| `build` | non | Commande lancée une seule fois avant les scénarios. Si elle échoue, tous les scénarios de cet adaptateur échouent. |
| `timeout` | non | Délai maximum par scénario, en secondes (10 par défaut). |

On passe par `build` plutôt que par `cargo run` pour ne pas payer le démarrage de cargo à chaque scénario.

## Lancer les tests

```bash
python3 conformance/runner/run.py                     # tout
python3 conformance/runner/run.py --adapter rust-A    # un seul adaptateur
python3 conformance/runner/run.py --filter a1/        # filtre sur le nom fonctionnalité/scénario
python3 conformance/runner/run.py -v                  # affiche aussi les succès
```

Codes de sortie : `0` si tout passe, `1` si un scénario échoue, `2` en cas d'erreur de configuration ou de scénario mal formé.

Les auto-tests du lanceur lui-même se lancent avec :

```bash
python3 -m unittest discover -s conformance/runner
```

## Hors de la v0

- **A3, symétrique** : il faudra un événement du genre `transfer <de> <vers>`, et peut-être une commande `start`.
- Les variantes B et D pourront demander d'autres commandes, comme `tick` pour faire avancer un exécuteur.
- Les valeurs structurées (paires, listes), si un scénario en a besoin.
