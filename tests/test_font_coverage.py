"""OEM XML regression checks; runs the actual installer awk/shell helper."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class FontCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="mfga-coverage-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.src = self.base / "source.xml"
        self.dest = self.base / "module/product/etc/fonts_customization.xml"
        self.shell = os.environ.get("MFGA_TEST_SHELL") or shutil.which("bash")
        self.assertTrue(self.shell)

    def run_helper(self, xml):
        self.src.write_text(xml, encoding="utf-8")
        return subprocess.run(
            [self.shell, "-c", '. "$1"; mfga_prepare_font_customization "$2" "$3" "$4"',
             "test", (ROOT / "script/font_coverage.sh").as_posix(),
             self.src.as_posix(), self.dest.as_posix(),
             (ROOT / "script/font_coverage.awk").as_posix()],
            capture_output=True, text=True)

    def test_nested_multiline_and_unrelated_content(self):
        untouched = '<family name="google-sans-clock" customizationType="new-named-family"><font>Clock.ttf</font></family>'
        xml = '''<?xml version="1.0"?>
<fonts-modification version="1">
<!-- comment with a fake </family> -->
<family-list name='google-sans-flex'
 customizationType = 'new-named-family'><family><font weight="700">A.ttf</font>
<font weight="400">A.ttf</font></family><family><font style="italic">B.ttf</font></family></family-list>
''' + untouched + '\n</fonts-modification>\n'
        result = self.run_helper(xml)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.dest.read_text(encoding="utf-8")
        self.assertIn(untouched, output)
        self.assertIn('<!-- comment with a fake </family> -->', output)
        alias = ET.fromstring(output).find("alias")
        self.assertEqual(alias.attrib, {"name": "google-sans-flex", "to": "sans-serif", "weight": "400"})
        self.assertNotIn("family-list", output)

    def test_weights_and_dependent_aliases(self):
        xml = '''<fonts-modification>
<alias name="other-medium" to="google-sans-text-medium" weight="600"/>
<alias name="google-sans-text-medium" to="google-sans-text" weight="500"/>
<family name="google-sans-text" customizationType="new-named-family"><font weight="400">A.ttf</font></family>
<family name="google-sans-bold" customizationType="new-named-family"><font weight="700">A.ttf</font></family>
<family name="variable-title-medium-emphasized" customizationType="new-named-family"><font weight="600">A.ttf</font></family>
</fonts-modification>'''
        result = self.run_helper(xml)
        self.assertEqual(result.returncode, 0, result.stderr)
        aliases = {a.get("name"): a.attrib for a in ET.parse(self.dest).findall("alias")}
        for name, weight in [("other-medium", "600"), ("google-sans-text-medium", "500"),
                             ("google-sans-bold", "700"), ("variable-title-medium-emphasized", "600")]:
            self.assertEqual(aliases[name]["weight"], weight)
            self.assertEqual(aliases[name]["to"], "sans-serif")

    def test_no_match_preserves_existing_destination(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_text("old", encoding="utf-8")
        xml = '''<fonts-modification><family name="google-sans-flex-clock" customizationType="new-named-family"><font>A.ttf</font></family>
<family name="google-sans-text-italic" customizationType="new-named-family"><font style="italic">B.ttf</font></family>
<family name="variable-icon-large" customizationType="new-named-family"><font>C.ttf</font></family></fonts-modification>'''
        result = self.run_helper(xml)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(self.dest.read_text(), "old")

    def test_idempotent(self):
        xml = '<fonts-modification><family name="google-sans" customizationType="new-named-family"><font>A.ttf</font></family></fonts-modification>'
        self.assertEqual(self.run_helper(xml).returncode, 0)
        before = self.dest.read_bytes()
        self.assertEqual(self.run_helper(before.decode()).returncode, 0)
        self.assertEqual(self.dest.read_bytes(), before)

    def test_bad_xml_never_replaces_destination(self):
        self.dest.parent.mkdir(parents=True)
        self.dest.write_text("old", encoding="utf-8")
        for xml in ['<familyset/>', '<fonts-modification><family></fonts-modification>',
                    '<fonts-modification><!-- unterminated',
                    '<!DOCTYPE fonts-modification><fonts-modification/>',
                    '<fonts-modification><family name="google-sans" customizationType="new-named-family"><font weight="9999">A.ttf</font></family></fonts-modification>']:
            with self.subTest(xml=xml):
                self.assertEqual(self.run_helper(xml).returncode, 1)
                self.assertEqual(self.dest.read_text(), "old")
                self.assertEqual(list(self.dest.parent.glob("*.coverage.*")), [])

    def test_installer_dispatch(self):
        # Source function definitions without the real /system scans.
        source = (ROOT / "script/search_dirs.sh").read_text(encoding="utf-8")
        source = source.split('search_and_copy "/system/system_ext/etc"')[0]
        fixture = self.base / "search.sh"
        fixture.write_text(source, encoding="utf-8", newline="\n")
        module = self.base / "module"
        (module / "lang").mkdir(parents=True)
        (module / "system").mkdir()
        (module / "lang/lang.sh").write_text("")
        (module / "fonts.xml").write_text('<familyset/>')
        shutil.copyfile(ROOT / "fonts_list.yaml", module / "fonts_list.yaml")
        shutil.copyfile(ROOT / "script/font_coverage.awk", module / "font_coverage.awk")
        custom = self.base / "fonts_customization.xml"
        custom.write_text('<fonts-modification><family name="google-sans" customizationType="new-named-family"><font>A.ttf</font></family></fonts-modification>')
        emoji = self.base / "fonts_customization_emoji.xml"
        emoji.write_text('<fonts-modification version="1"/>')
        normal = self.base / "font_fallback.xml"
        normal.write_text('<familyset/>')
        result = subprocess.run([self.shell, "-c",
            'MODPATH="$1"; abort() { exit 99; }; . "$2"; . "$3"; handle_file "$4" "product/etc"; handle_file "$5" "product/etc"; handle_file "$6" "etc"',
            "test", module.as_posix(), (ROOT / "script/font_coverage.sh").as_posix(),
            fixture.as_posix(), custom.as_posix(), emoji.as_posix(), normal.as_posix()],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ET.parse(module / "system/product/etc/fonts_customization.xml").getroot().tag, "fonts-modification")
        self.assertFalse((module / "system/product/etc/fonts_customization_emoji.xml").exists())
        self.assertTrue((module / "system/etc/font_fallback.xml").exists())
