import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
import package_extension


class PackageTests(unittest.TestCase):
    def fixture(self, root):
        source=root/'source'
        source.mkdir()
        (source/'manifest.json').write_text(json.dumps({'name':'Zotero Connector (MCP Bridge)',
                                                      'manifest_version':3,'version':'4.999.1'}))
        bridge=Path(package_extension.__file__).with_name('bridge-background.js').read_text(encoding='utf-8')
        (source/'background.js').write_text(bridge,encoding='utf-8')
        return source

    def test_private_pairing_excluded_and_source_unchanged(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp)
            source=self.fixture(root)
            (source/'mcp-private-config.json').write_text('{"token":"test-private"}')
            before=(source/'manifest.json').read_bytes()
            result=package_extension.package(source,root/'out','2.1.1')
            with ZipFile(root/'out'/result['archive']) as archive:
                self.assertNotIn('mcp-private-config.json',archive.namelist())
                self.assertIn('SOURCE.md',archive.namelist())
                self.assertIn('INSTALL.txt',archive.namelist())
                self.assertIn('2.1.1',json.loads(archive.read('manifest.json'))['version_name'])
            self.assertEqual(before,(source/'manifest.json').read_bytes())
            self.assertEqual(len(result['sha256']),64)

    def test_private_path_in_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp)
            source=self.fixture(root)
            (source/'example.js').write_text('"'+'/'.join(['C:','Users','example','private'])+'"')
            with self.assertRaises(ValueError):
                package_extension.package(source,root/'out','2.1.1')

    def test_mismatched_bridge_build_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            root=Path(tmp)
            source=self.fixture(root)
            (source/'background.js').write_text('// different bridge')
            with self.assertRaises(ValueError):
                package_extension.package(source,root/'out','2.1.1')
