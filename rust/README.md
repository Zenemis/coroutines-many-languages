# Coroutines en Rust

Il y a plusieurs façons de « faire des coroutines » en Rust. Elles ne mettent pas la difficulté au même endroit. Chaque dossier correspond à une variante, et le but est de toutes les faire à terme.

| Dossier | Variante | Qui écrit la machine à états ? | Où est l'état suspendu ? | Ce qu'on apprend |
|---|---|---|---|---|
| [`A-machine-a-etats`](A-machine-a-etats/) | Machine à états explicite | Moi, à la main | Dans une valeur (souvent un `enum`) | Le système de types : possession, durées de vie, encoder « terminé » |
| [`B-executeur-async`](B-executeur-async/) | Mini-exécuteur pour `async`/`await` | Le compilateur (`rustc`) | Dans le `Future` généré | L'ordonnancement, `Waker`, `Pin`, les files de tâches |
| [`C-macro-generatrice`](C-macro-generatrice/) | Macro qui génère la machine à états | Ma macro | Dans le type généré par la macro | La métaprogrammation, l'absence de `goto` en Rust |
| [`D-stackful`](D-stackful/) | Coroutines avec leur propre pile | Personne : il n'y a pas de machine à états | Dans une pile allouée à part | Les conventions d'appel, l'assembleur inline, `unsafe` |

## Les deux grandes familles

**Stackless (A, B, C).** Une coroutine suspendue n'a pas de pile à elle. Ses variables vivantes et son « numéro d'étape » sont rangés dans une valeur ordinaire. Reprendre la coroutine, c'est appeler une fonction sur cette valeur, qui saute à la bonne étape. C'est le modèle de Kotlin, C#, Python et Rust `async`, et aussi celui des macros de Simon Tatham en C.

Conséquence : on ne peut se suspendre que dans le corps de la coroutine lui-même, pas depuis une fonction ordinaire qu'elle appelle.

**Stackful (D).** Chaque coroutine a sa propre pile. Pour se suspendre, on sauvegarde les registres, on change le pointeur de pile et on saute dans une autre coroutine. On peut se suspendre n'importe où, même au fond d'une pile d'appels. C'est le modèle de Go, Lua et des threads virtuels Java.

## A, B et C : en quoi elles diffèrent

Ces trois variantes sont stackless. La différence est de savoir qui fait la transformation « fonction → machine à états » :

- **A** : je l'écris moi-même. C'est verbeux, mais rien n'est caché. C'est l'équivalent de la classe que génère le compilateur C# pour un itérateur.
- **B** : `rustc` la fait pour chaque `async fn`. Le travail intéressant, c'est ce qui tourne autour : celui qui appelle `poll`, et qui décide quand rappeler. C'est le rôle du `main` dans l'exemple du cuisinier et du serveur.
- **C** : une macro la fait à ma place. C'est l'équivalent des macros de Tatham, mais Rust n'a ni `goto` ni `case` qu'on peut glisser au milieu d'une boucle. Il faut donc trouver autre chose.

## Feuille de route de A

On avance du plus simple au plus riche :

1. **A1 — Asymétrique, sans valeur de reprise.** La coroutine rend la main à celui qui l'a reprise. Elle produit des valeurs avec `yield`, puis une valeur finale. On la reprend sans rien lui envoyer.
2. **A2 — Asymétrique, avec valeur de reprise.** Comme A1, mais chaque reprise envoie une valeur dans la coroutine, comme `send` en Python. On manipule donc trois types : ce qui entre, ce qui sort avec `yield` et ce qui est renvoyé à la fin.
3. **A3 — Symétrique.** Une coroutine passe la main directement à une autre, sans repasser par l'appelant, comme chez Conway.

### Décisions déjà prises

- **La sémantique suit `std::ops::Coroutine`**, mais pas sa syntaxe : A est une bibliothèque, pas une macro ni une extension du compilateur. Par conséquent :
  - reprendre une coroutine terminée **panique** ;
  - en A2, la valeur du premier `resume` est reçue par le corps comme paramètre de départ ;
  - abandonner une coroutine suspendue détruit ses variables encore vivantes.
- **Oracle différentiel** : en plus des tests de conformité, chaque corps du catalogue est réécrit une seconde fois avec `std::ops::Coroutine` (nightly). Les deux versions doivent produire les mêmes traces.

### Questions ouvertes

- **Qui possède l'état de la coroutine ?** La coroutine elle-même, l'appelant, un ordonnanceur ? C'est l'un des problèmes à résoudre.
- Peut-on garder une référence vers une donnée de la coroutine au-delà d'un `yield` ? Si non, pourquoi ?
- Le système de types peut-il rendre impossible, et pas seulement fautif, le fait de reprendre une coroutine terminée ? Et faut-il le vouloir ?
- En A3, qui est responsable de la coroutine qui reçoit la main ?

## Crates

| Crate | Toolchain | Contenu |
|---|---|---|
| [`A-machine-a-etats`](A-machine-a-etats/) (`coroutines-a`) | stable | La bibliothèque (`src/lib.rs`) et son adaptateur de conformité (`src/bin/adapter.rs`) |
| [`oracle-std`](oracle-std/) | nightly (via `rust-toolchain.toml`) | Les corps du catalogue écrits avec `std::ops::Coroutine`, derrière le même protocole (`src/bin/adapter.rs`) |

Les crates sont indépendantes, sans workspace, parce qu'un workspace imposerait la même toolchain à toutes.

## Tests

- Les tests unitaires propres à Rust vivent dans chaque crate (`cargo test`).
- Les adaptateurs sont déclarés dans [`../conformance/adapters.json`](../conformance/adapters.json) sous les noms `rust-A` et `oracle-rust-std`. Le niveau différentiel consiste à faire passer les mêmes scénarios aux deux :

  ```bash
  python3 conformance/runner/run.py --adapter rust-A --adapter oracle-rust-std
  ```
- Le comportement commun à tous les langages est vérifié par les tests de conformité de [`../conformance`](../conformance/).
