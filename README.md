# coroutines-many-languages

Réimplémentations simples des coroutines dans plusieurs langages, écrites à la main pour comprendre comment elles fonctionnent.

Démarche pour chaque langage :

1. concevoir l'API ;
2. écrire les tests (en langage naturel d'abord, TDD) ;
3. écrire l'implémentation à la main.

## Organisation

- [`rust/`](rust/) : quatre variantes (machine à états, exécuteur async, macro, stackful).
- [`conformance/`](conformance/) : tests de comportement communs à tous les langages.
