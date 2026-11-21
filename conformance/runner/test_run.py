"""Auto-tests du lanceur. Lancer avec : python3 -m unittest discover conformance/runner"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402

# Faux adaptateur : chaque `resume X` produit `yield <compteur de X>`,
# `crash` sort avec le code 3, `sleep` bloque, le reste est ignoré.
FAKE_ADAPTER = textwrap.dedent(
    """
    import sys, time
    counts = {}
    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "resume":
            n = counts.get(parts[1], 0)
            counts[parts[1]] = n + 1
            print("yield", n)
        elif parts[0] == "crash":
            print("boum", file=sys.stderr)
            sys.exit(3)
        elif parts[0] == "sleep":
            time.sleep(5)
    """
)


class Workspace:
    """Un faux dépôt dans un dossier temporaire."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.scenarios = self.root / "scenarios"
        self.scenarios.mkdir()
        impl = self.root / "impl"
        impl.mkdir()
        (impl / "adapter.py").write_text(FAKE_ADAPTER)
        self.config = self.root / "adapters.json"

    def close(self) -> None:
        self._tmp.cleanup()

    def scenario(self, feature: str, name: str, body: str) -> Path:
        d = self.scenarios / feature
        d.mkdir(exist_ok=True)
        p = d / f"{name}.scn"
        p.write_text(textwrap.dedent(body))
        return p

    def adapters(self, **entries: dict) -> None:
        self.config.write_text(json.dumps({"adapters": entries}))

    def fake(self, features=("a1",), **extra) -> dict:
        entry = {"cwd": "impl", "command": [sys.executable, "adapter.py"], "features": list(features)}
        entry.update(extra)
        return entry

    def main(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = run.main([
                "--config", str(self.config),
                "--scenarios", str(self.scenarios),
                "--repo-root", str(self.root),
                *args,
            ])
        return code, out.getvalue()


class ParseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Workspace()

    def tearDown(self) -> None:
        self.ws.close()

    def test_lit_titre_commandes_et_attendus(self) -> None:
        p = self.ws.scenario("a1", "s", """\
            # Mon titre
            # description

            > new compteur 2 as c
            > resume c
            < yield 0
            < print Cuisinier : je coupe
            """)
        s = run.parse_scenario(p, "a1")
        self.assertEqual(s.title, "Mon titre")
        self.assertEqual(s.commands, ["new compteur 2 as c", "resume c"])
        self.assertEqual(s.expected, ["yield 0", "print Cuisinier : je coupe"])
        self.assertEqual(s.name, "a1/s")

    def test_ligne_inconnue_refusee(self) -> None:
        p = self.ws.scenario("a1", "s", "> resume c\nyield 0\n")
        with self.assertRaisesRegex(run.ScenarioError, ":2:"):
            run.parse_scenario(p, "a1")

    def test_sans_commande_refuse(self) -> None:
        p = self.ws.scenario("a1", "s", "# rien\n< yield 0\n")
        with self.assertRaises(run.ScenarioError):
            run.parse_scenario(p, "a1")

    def test_scenario_hors_dossier_signale(self) -> None:
        (self.ws.scenarios / "perdu.scn").write_text("> resume c\n")
        self.ws.scenario("a2", "x", "> resume c\n")
        scenarios, warnings = run.discover_scenarios(self.ws.scenarios)
        self.assertEqual([s.name for s in scenarios], ["a2/x"])
        self.assertEqual(len(warnings), 1)


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Workspace()

    def tearDown(self) -> None:
        self.ws.close()

    def test_cwd_relatif_a_la_racine(self) -> None:
        self.ws.adapters(fake=self.ws.fake())
        [a] = run.load_adapters(self.ws.config, self.ws.root)
        self.assertEqual(a.cwd, (self.ws.root / "impl").resolve())
        self.assertIsNone(a.build)

    def test_champ_manquant_refuse(self) -> None:
        self.ws.adapters(fake={"cwd": "impl", "features": ["a1"]})
        with self.assertRaisesRegex(run.ConfigError, "command"):
            run.load_adapters(self.ws.config, self.ws.root)

    def test_aucun_adaptateur(self) -> None:
        self.ws.adapters()
        code, out = self.ws.main()
        self.assertEqual(code, 0)
        self.assertIn("Aucun adaptateur", out)


class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Workspace()

    def tearDown(self) -> None:
        self.ws.close()

    def test_succes(self) -> None:
        self.ws.scenario("a1", "ok", "> resume c\n< yield 0\n> resume c\n< yield 1\n")
        self.ws.adapters(fake=self.ws.fake())
        code, out = self.ws.main()
        self.assertEqual(code, 0, out)
        self.assertIn("1/1", out)

    def test_sortie_differente_affiche_un_diff(self) -> None:
        self.ws.scenario("a1", "ko", "> resume c\n< yield 42\n")
        self.ws.adapters(fake=self.ws.fake())
        code, out = self.ws.main()
        self.assertEqual(code, 1)
        self.assertIn("-yield 42", out)
        self.assertIn("+yield 0", out)

    def test_code_de_sortie_non_nul_echoue_meme_si_sortie_identique(self) -> None:
        self.ws.scenario("a1", "crash", "> resume c\n< yield 0\n> crash\n")
        self.ws.adapters(fake=self.ws.fake())
        code, out = self.ws.main()
        self.assertEqual(code, 1)
        self.assertIn("code de sortie 3", out)
        self.assertIn("boum", out)

    def test_delai_depasse(self) -> None:
        self.ws.scenario("a1", "lent", "> sleep\n")
        self.ws.adapters(fake=self.ws.fake(timeout=0.5))
        code, out = self.ws.main()
        self.assertEqual(code, 1)
        self.assertIn("délai dépassé", out)

    def test_seules_les_fonctionnalites_supportees_sont_lancees(self) -> None:
        self.ws.scenario("a1", "un", "> resume c\n< yield 0\n")
        self.ws.scenario("a2", "deux", "> resume c\n< faux\n")
        self.ws.adapters(fake=self.ws.fake(features=["a1"]))
        code, out = self.ws.main("-v")
        self.assertEqual(code, 0, out)
        self.assertIn("a1/un", out)
        self.assertNotIn("a2/deux", out)

    def test_filtre(self) -> None:
        self.ws.scenario("a1", "garde", "> resume c\n< yield 0\n")
        self.ws.scenario("a1", "jete", "> resume c\n< faux\n")
        self.ws.adapters(fake=self.ws.fake())
        code, out = self.ws.main("--filter", "garde")
        self.assertEqual(code, 0, out)

    def test_build_en_echec_fait_echouer_les_scenarios(self) -> None:
        self.ws.scenario("a1", "s", "> resume c\n< yield 0\n")
        self.ws.adapters(fake=self.ws.fake(build=[sys.executable, "-c", "import sys; sys.exit(1)"]))
        code, out = self.ws.main()
        self.assertEqual(code, 1)
        self.assertIn("build en échec", out)

    def test_executable_relatif_resolu_depuis_cwd(self) -> None:
        exe = self.ws.root / "impl" / "bin" / "adapter"
        exe.parent.mkdir()
        exe.write_text(f"#!{sys.executable}\n" + FAKE_ADAPTER)
        exe.chmod(0o755)
        self.ws.scenario("a1", "s", "> resume c\n< yield 0\n")
        self.ws.adapters(fake={"cwd": "impl", "command": ["bin/adapter"], "features": ["a1"]})
        code, out = self.ws.main()
        self.assertEqual(code, 0, out)

    def test_adaptateur_inconnu(self) -> None:
        self.ws.adapters(fake=self.ws.fake())
        code, _ = self.ws.main("--adapter", "nope")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
