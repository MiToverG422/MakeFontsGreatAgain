"""Installer regression checks; synthetic SFNT headers need no fontTools.

Run: python3 -m unittest discover -s tests
Set MFGA_TEST_SHELL to a POSIX shell if bash is not on PATH (e.g. Git Bash).
"""
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = (
    "NotoSerifHebrew", "NotoSerifThai", "NotoSansGujarati",
    "NotoSansOriya", "NotoSansLao", "NotoSerifLao",
)


def sfnt(axes=(), offset=28, signature=b"\x00\x01\x00\x00"):
    header = signature + struct.pack(">HHHH", 1, 16, 0, 0)
    if not axes:
        return header + struct.pack(">4sIII", b"name", 0, 28, 0)
    table = struct.pack(">HHHHHHHH", 1, 0, 16, 2, len(axes), 20, 0, 4)
    for tag, minimum, default, maximum in axes:
        table += struct.pack(">4siiiHH", tag.encode(), int(minimum * 65536),
                             int(default * 65536), int(maximum * 65536), 0, 256)
    directory = struct.pack(">4sIII", b"fvar", 0, offset, len(table))
    return header + directory + bytes(offset - 28) + table


class FontCompatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mfga-font-compat-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.system = self.base / "system-fonts"
        self.module = self.base / "module-fonts"
        self.system.mkdir()
        self.module.mkdir()
        self.xml = self.base / "fonts.xml"
        shutil.copyfile(ROOT / "fonts.xml", self.xml)
        self.shell = os.environ.get("MFGA_TEST_SHELL") or shutil.which("bash")
        self.assertTrue(self.shell, "A POSIX shell is required")

    def run_shell(self, command, *args):
        return subprocess.run(
            [self.shell, "-c", '. "$1"; shift; ' + command, "test",
             (ROOT / "script/font_compat.sh").as_posix(),
             *[str(arg).replace("\\", "/") for arg in args]],
            capture_output=True, text=True,
        )

    def prepare(self):
        result = self.run_shell('mfga_prepare_font_config "$1" "$2" "$3"',
                                self.xml, self.module, self.system)
        self.assertEqual(result.returncode, 0, result.stderr)

    def fill_regulars(self, data):
        for prefix in PREFIXES:
            (self.system / (prefix + "-Regular.ttf")).write_bytes(data)

    def assert_bold_form(self, variable):
        tree = ET.parse(self.xml)
        for prefix in PREFIXES:
            entries = [font for font in tree.findall(".//font")
                       if font.get("weight") == "700"
                       and (font.text or "").strip().startswith(prefix + "-")]
            self.assertEqual(len(entries), 1, prefix)
            font = entries[0]
            self.assertEqual(font.text.strip(), prefix + ("-Regular.ttf" if variable else "-Bold.ttf"))
            self.assertEqual([axis.attrib for axis in font],
                             [{"tag": "wght", "stylevalue": "700"}] if variable else [])
            self.assertEqual(font.get("fallbackFor"), "serif" if "Serif" in prefix else None)

    def test_variable_regular_keeps_explicit_weight_and_is_idempotent(self):
        self.fill_regulars(sfnt([("wght", 100, 400, 900)]))
        self.prepare()
        self.assert_bold_form(True)
        first = self.xml.read_bytes()
        self.prepare()
        self.assertEqual(first, self.xml.read_bytes())
        # No unrelated XML changes on the ROM for which this fix was developed.
        self.assertEqual(self.xml.read_text(encoding="utf-8"),
                         (ROOT / "fonts.xml").read_text(encoding="utf-8"))

    def test_static_rom_restores_bold_files(self):
        self.fill_regulars(sfnt())
        self.prepare()
        self.assert_bold_form(False)
        first = self.xml.read_bytes()
        self.prepare()
        self.assertEqual(first, self.xml.read_bytes())

    def test_incoming_module_takes_precedence_over_system(self):
        self.fill_regulars(sfnt([("wght", 100, 400, 900)]))
        for prefix in PREFIXES:
            (self.module / (prefix + "-Regular.ttf")).write_bytes(sfnt())
        self.prepare()
        self.assert_bold_form(False)

    def test_missing_regular_keeps_legacy_mapping(self):
        self.prepare()
        self.assert_bold_form(False)

    def test_axis_without_700_is_not_selected(self):
        self.fill_regulars(sfnt([("wght", 100, 400, 600)]))
        self.prepare()
        self.assert_bold_form(False)

    def test_second_axis_cff_and_distant_table(self):
        path = self.system / "probe.ttf"
        path.write_bytes(sfnt([("wdth", 75, 100, 125), ("wght", 100, 400, 900)],
                              offset=70000, signature=b"OTTO"))
        result = self.run_shell('mfga_supports_bold_axis "$1"', path)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_or_unrelated_axis_is_rejected(self):
        path = self.system / "probe.ttf"
        for data in (b"", b"ttcf" + bytes(40), sfnt([("wdth", 75, 100, 125)]),
                     sfnt([("wght", 100, 400, 900)])[:-1],
                     sfnt([("wght", 900, 400, 100)])):
            with self.subTest(data=data[:16]):
                path.write_bytes(data)
                result = self.run_shell('mfga_supports_bold_axis "$1"', path)
                self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
