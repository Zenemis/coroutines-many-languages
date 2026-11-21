# Catalogue des corps de coroutines

Chaque corps est décrit ici **une seule fois**, en langage naturel. Chaque adaptateur le réécrit ensuite dans son langage, **avec l'implémentation de coroutine testée**.

Les corps doivent rester **triviaux**. Le seul code non trivial exécuté pendant un test doit être la mécanique de coroutine (suspension, reprise, fin, abandon), pas le corps lui-même.

Pour chaque corps, un pseudo-code dans le style de `std::ops::Coroutine` sert de référence. `yield x` suspend en produisant `x`. En A2, `yield x` vaut la valeur envoyée par le `resume` suivant.

---

## Corps A1 (reprise sans valeur)

### `feu <cycles>`

Un feu tricolore qui fait `cycles` tours, puis s'éteint.

```
print "allumage"
répéter cycles fois :
    yield vert ; yield orange ; yield rouge
return eteint
```

Ce qu'il permet d'observer :
- la reprise continue au bon endroit, et le compteur de boucle survit aux suspensions ;
- une valeur finale est bien transmise ;
- avec `cycles = 0`, la coroutine se termine dès la première reprise sans jamais faire de `yield`.

### `tache <nom> <etapes>`

Une tâche qui annonce chacune de ses étapes : c'est le cuisinier et le serveur.

```
pour i de 1 à etapes :
    print "<nom> etape <i>"
    yield i
return            (sans valeur)
```

Ce qu'il permet d'observer :
- le démarrage paresseux : rien ne s'affiche avant le premier `resume` ;
- l'entrelacement de plusieurs instances ;
- une fin sans valeur.

### `ressource`

Une tâche qui prend une ressource et la libère quand sa variable est détruite.

```
print "debut"
garde ← une valeur qui affiche « liberation » quand elle est détruite
yield 1
yield 2
return            (sans valeur ; garde est détruite juste avant)
```

En Rust, `garde` est une valeur dont l'implémentation de `Drop` émet `print liberation`. En Python, c'est un bloc `try … finally`.

Ce qu'il permet d'observer :
- abandonnée **pendant** une suspension, elle libère sa ressource ;
- abandonnée **avant** de démarrer, ou **après** la fin, elle n'affiche rien ;
- en fin normale, `liberation` sort **avant** l'événement `return`.

---

## Corps A2 (reprise avec valeur)

### `echo`

Renvoie chaque valeur reçue, jusqu'à recevoir `stop`.

```
v ← valeur du premier resume
tant que v ≠ stop :
    v ← yield v
return fini
```

Ce qu'il permet d'observer :
- la valeur du **premier** `resume` n'est pas perdue ;
- chaque valeur arrive dans l'ordre ;
- la fin peut être déclenchée par une valeur reçue.

### `accumulateur`

Additionne tout ce qu'il reçoit, à l'infini. Les valeurs sont des entiers.

```
total ← valeur du premier resume
boucle :
    v ← yield total
    total ← total + v
```

Ce qu'il permet d'observer :
- un état local qui dépend des valeurs reçues survit aux suspensions ;
- deux instances ont chacune leur propre total.
