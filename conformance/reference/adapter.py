#!/usr/bin/env python3
"""Adaptateur de RÉFÉRENCE : valide les scénarios eux-mêmes (voir ../README.md).

Il utilise les générateurs natifs de Python comme implémentation de coroutine,
et les plie à la sémantique de std::ops::Coroutine (voir ../PROTOCOLE.md) :
  - reprendre une instance terminée -> `panic` ;
  - en A2, la valeur du premier resume est passée comme paramètre au corps.
"""

import sys


def emit(line):
    """Écrit un événement sur stdout : une ligne = un événement."""
    print(line)


# ---------------------------------------------------------------------------
# Le catalogue (voir ../CATALOGUE.md). Les corps A2 reçoivent la valeur du
# premier resume en premier paramètre.
# ---------------------------------------------------------------------------

def feu(cycles):
    emit("print allumage")
    for _ in range(int(cycles)):
        yield "vert"
        yield "orange"
        yield "rouge"
    return "eteint"


def tache(nom, etapes):
    for i in range(1, int(etapes) + 1):
        emit(f"print {nom} etape {i}")
        yield i


def ressource():
    emit("print debut")
    try:                      # le `finally` joue le rôle du Drop de `garde`
        yield 1
        yield 2
    finally:
        emit("print liberation")


def echo(v):
    while v != "stop":
        v = yield v
    return "fini"


def accumulateur(total):
    total = int(total)
    while True:
        v = yield total
        total += int(v)


CATALOGUE = {
    "feu": feu,
    "tache": tache,
    "ressource": ressource,
    "echo": echo,
    "accumulateur": accumulateur,
}


# ---------------------------------------------------------------------------
# Une instance : le générateur n'est créé qu'au premier resume, pour pouvoir
# lui passer la première valeur (A2) comme le fait std::ops::Coroutine.
# ---------------------------------------------------------------------------

class Instance:
    def __init__(self, body, args):
        self.body = body
        self.args = args
        self.gen = None
        self.done = False

    def resume(self, value):
        if self.done:
            emit("panic")
            return
        try:
            if self.gen is None:
                first = [] if value is None else [value]
                self.gen = self.body(*first, *self.args)
                out = next(self.gen)
            else:
                out = self.gen.send(value)
            emit(f"yield {out}")
        except StopIteration as fin:
            self.done = True
            emit("return" if fin.value is None else f"return {fin.value}")

    def drop(self):
        if self.gen is not None:
            self.gen.close()      # exécute les `finally` encore en attente


instances = {}


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        cmd, *args = line.split()

        if cmd == "new":                          # new <corps> [arg…] as <nom>
            *body_args, _as, name = args
            body, *params = body_args
            instances[name] = Instance(CATALOGUE[body], params)

        elif cmd == "resume":                     # resume <nom> [valeur]
            name, *value = args
            if name not in instances:
                emit(f"error unknown {name}")
            else:
                instances[name].resume(value[0] if value else None)

        elif cmd == "drop":                       # drop <nom>
            name = args[0]
            if name not in instances:
                emit(f"error unknown {name}")
            else:
                instances.pop(name).drop()


if __name__ == "__main__":
    main()
