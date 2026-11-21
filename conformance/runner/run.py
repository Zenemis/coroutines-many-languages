#!/usr/bin/env python3
"""Lanceur des tests de conformité (voir conformance/PROTOCOLE.md).

Pour chaque adaptateur déclaré dans conformance/adapters.json, il :
  1. lance la commande de build, une seule fois ;
  2. pour chaque scénario d'une fonctionnalité que l'adaptateur supporte,
     envoie toutes les commandes `>` sur stdin et compare stdout aux lignes `<`.

Usage :
  python3 conformance/runner/run.py [--adapter NOM] [--filter TEXTE] [-v]
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

CONFORMANCE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = CONFORMANCE_DIR.parent
DEFAULT_CONFIG = CONFORMANCE_DIR / "adapters.json"
DEFAULT_SCENARIOS = CONFORMANCE_DIR / "scenarios"
DEFAULT_TIMEOUT = 10.0


class ScenarioError(Exception):
    """Fichier de scénario mal formé."""


class ConfigError(Exception):
    """Fichier adapters.json mal formé."""


@dataclass
class Scenario:
    path: Path
    feature: str
    title: str
    commands: list[str] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.feature}/{self.path.stem}"


@dataclass
class Adapter:
    name: str
    cwd: Path
    command: list[str]
    features: list[str]
    build: list[str] | None = None
    timeout: float = DEFAULT_TIMEOUT


@dataclass
class Result:
    scenario: Scenario
    ok: bool
    detail: str = ""


# --------------------------------------------------------------------------
# Lecture des scénarios
# --------------------------------------------------------------------------

def parse_scenario(path: Path, feature: str) -> Scenario:
    title = ""
    scenario = Scenario(path=path, feature=feature, title="")
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("#"):
            if not title:
                title = line.lstrip("#").strip()
            continue
        if line.startswith("> "):
            scenario.commands.append(line[2:])
        elif line.startswith("< "):
            scenario.expected.append(line[2:])
        elif line in (">", "<"):
            raise ScenarioError(f"{path}:{lineno}: ligne `{line}` vide")
        else:
            raise ScenarioError(
                f"{path}:{lineno}: ligne inattendue (attendu `#`, `> ` ou `< `) : {raw!r}"
            )
    if not scenario.commands:
        raise ScenarioError(f"{path}: aucune commande `>`")
    scenario.title = title or path.stem
    return scenario


def discover_scenarios(root: Path) -> tuple[list[Scenario], list[str]]:
    """Renvoie les scénarios trouvés dans root/<fonctionnalité>/*.scn, plus des avertissements."""
    scenarios: list[Scenario] = []
    warnings: list[str] = []
    if not root.is_dir():
        return scenarios, [f"dossier de scénarios introuvable : {root}"]
    for stray in sorted(root.glob("*.scn")):
        warnings.append(
            f"{stray.relative_to(root)} ignoré : un scénario doit être rangé "
            "dans un sous-dossier de fonctionnalité (ex. scenarios/a1/)"
        )
    for feature_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for path in sorted(feature_dir.glob("*.scn")):
            scenarios.append(parse_scenario(path, feature_dir.name))
    return scenarios, warnings


# --------------------------------------------------------------------------
# Configuration des adaptateurs
# --------------------------------------------------------------------------

def _str_list(value: object, where: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value) or not value:
        raise ConfigError(f"{where} doit être une liste non vide de chaînes")
    return value


def load_adapters(config_path: Path, repo_root: Path) -> list[Adapter]:
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"configuration introuvable : {config_path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"{config_path}: JSON invalide : {e}")

    entries = data.get("adapters") if isinstance(data, dict) else None
    if not isinstance(entries, dict):
        raise ConfigError(f"{config_path}: clé `adapters` (objet) manquante")

    adapters = []
    for name, entry in entries.items():
        where = f"{config_path.name}: adapters.{name}"
        if not isinstance(entry, dict):
            raise ConfigError(f"{where} doit être un objet")
        cwd = entry.get("cwd")
        if not isinstance(cwd, str):
            raise ConfigError(f"{where}.cwd doit être une chaîne (relative à la racine du dépôt)")
        build = entry.get("build")
        timeout = entry.get("timeout", DEFAULT_TIMEOUT)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ConfigError(f"{where}.timeout doit être un nombre positif")
        adapters.append(
            Adapter(
                name=name,
                cwd=(repo_root / cwd).resolve(),
                command=_str_list(entry.get("command"), f"{where}.command"),
                features=_str_list(entry.get("features"), f"{where}.features"),
                build=_str_list(build, f"{where}.build") if build is not None else None,
                timeout=float(timeout),
            )
        )
    return adapters


# --------------------------------------------------------------------------
# Exécution
# --------------------------------------------------------------------------

def _resolve_command(adapter: Adapter) -> list[str]:
    """Un exécutable donné en chemin relatif (ex. target/debug/adapter) est relatif à cwd."""
    exe, *rest = adapter.command
    if "/" in exe and not Path(exe).is_absolute():
        exe = str(adapter.cwd / exe)
    return [exe, *rest]


def build_adapter(adapter: Adapter) -> str | None:
    """Renvoie un message d'erreur si le build échoue, sinon None."""
    if adapter.build is None:
        return None
    try:
        proc = subprocess.run(adapter.build, cwd=adapter.cwd, capture_output=True, text=True)
    except OSError as e:
        return f"build impossible : {e}"
    if proc.returncode != 0:
        return f"build en échec (code {proc.returncode})\n{proc.stdout}{proc.stderr}"
    return None


def run_scenario(adapter: Adapter, scenario: Scenario) -> Result:
    stdin = "".join(c + "\n" for c in scenario.commands)
    try:
        proc = subprocess.run(
            _resolve_command(adapter),
            cwd=adapter.cwd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=adapter.timeout,
        )
    except subprocess.TimeoutExpired:
        return Result(scenario, False, f"délai dépassé ({adapter.timeout:g} s)")
    except OSError as e:
        return Result(scenario, False, f"lancement impossible : {e}")

    actual = [line.rstrip("\r") for line in proc.stdout.splitlines()]
    problems = []
    if proc.returncode != 0:
        problems.append(f"code de sortie {proc.returncode} (attendu 0)")
    if actual != scenario.expected:
        diff = difflib.unified_diff(
            scenario.expected, actual, fromfile="attendu", tofile="obtenu", lineterm=""
        )
        problems.append("sortie différente :\n" + "\n".join(diff))
    if problems and proc.stderr.strip():
        problems.append("stderr :\n" + proc.stderr.rstrip())
    return Result(scenario, not problems, "\n".join(problems))


# --------------------------------------------------------------------------
# Interface
# --------------------------------------------------------------------------

def _indent(text: str) -> str:
    return "\n".join("      " + line for line in text.splitlines())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lance les tests de conformité.")
    parser.add_argument("--adapter", action="append", help="ne lancer que cet adaptateur (répétable)")
    parser.add_argument("--filter", help="ne lancer que les scénarios dont le nom contient ce texte")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("-v", "--verbose", action="store_true", help="afficher aussi les succès")
    args = parser.parse_args(argv)

    try:
        adapters = load_adapters(args.config, args.repo_root)
        scenarios, warnings = discover_scenarios(args.scenarios)
    except (ConfigError, ScenarioError) as e:
        print(f"erreur : {e}", file=sys.stderr)
        return 2

    for w in warnings:
        print(f"attention : {w}", file=sys.stderr)

    if args.adapter:
        unknown = set(args.adapter) - {a.name for a in adapters}
        if unknown:
            print(f"erreur : adaptateur(s) inconnu(s) : {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
        adapters = [a for a in adapters if a.name in args.adapter]
    if args.filter:
        scenarios = [s for s in scenarios if args.filter in s.name]

    if not adapters:
        print("Aucun adaptateur déclaré dans", args.config)
        return 0

    total_failed = 0
    total_run = 0
    for adapter in adapters:
        selected = [s for s in scenarios if s.feature in adapter.features]
        print(f"== {adapter.name}  ({', '.join(adapter.features)} ; {len(selected)} scénario(s))")
        if not selected:
            continue
        build_error = build_adapter(adapter)
        if build_error:
            print(_indent(build_error))
            total_failed += len(selected)
            total_run += len(selected)
            continue
        for scenario in selected:
            result = run_scenario(adapter, scenario)
            total_run += 1
            if result.ok:
                if args.verbose:
                    print(f"  ok    {scenario.name} — {scenario.title}")
            else:
                total_failed += 1
                print(f"  ÉCHEC {scenario.name} — {scenario.title}")
                print(_indent(result.detail))

    print(f"\n{total_run - total_failed}/{total_run} réussi(s)")
    return 1 if total_failed else 0


if __name__ == "__main__":
    sys.exit(main())
