from pathlib import Path
from unittest import TestCase


class TestNativeInstallPackaging(TestCase):
    def test_entrypoints_include_native_builder(self):
        self.assertIn(
            'dirsearch-build-native = "dirsearch.lib.core.native_builder:main"',
            Path("pyproject.toml").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "dirsearch-build-native=dirsearch.lib.core.native_builder:main",
            Path("setup.py").read_text(encoding="utf-8"),
        )

    def test_package_data_includes_native_sources(self):
        setup_py = Path("setup.py").read_text(encoding="utf-8")

        self.assertIn('*package_files(package_root / "native")', setup_py)
        self.assertIn('"target"', setup_py)

    def test_install_docs_use_native_builder_flow(self):
        docs = Path("docs/installation.md").read_text(encoding="utf-8")

        self.assertIn("dirsearch-build-native", docs)
        self.assertIn("python3.14-dev", docs)
        self.assertIn("python3.14-devel", docs)
        self.assertNotIn("maturin develop", docs)
