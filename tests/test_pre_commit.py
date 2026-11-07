"""Regression tests for upstream archive extraction safety."""
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HOOK = Path(__file__).resolve().parents[1] / "git-hooks" / "pre-commit.py"
spec = importlib.util.spec_from_file_location("chain_love_pre_commit", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def archive_for(name, *, kind="file", content=b"ok"):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as tar:
        root = tarfile.TarInfo("repo-root/")
        root.type = tarfile.DIRTYPE
        tar.addfile(root)
        entry = tarfile.TarInfo(name)
        if kind == "symlink":
            entry.type = tarfile.SYMTYPE
            entry.linkname = "../../outside"
            tar.addfile(entry)
        else:
            entry.size = len(content)
            tar.addfile(entry, io.BytesIO(content))
    return stream.getvalue()


class TestSafeUpstreamExtraction(unittest.TestCase):
    def extract(self, payload, dest):
        with patch.object(hook.urllib.request, "urlopen", return_value=io.BytesIO(payload)):
            hook.download_and_extract("https://example.invalid/archive.tar.gz", dest, "tools/*")

    def test_valid_file_is_extracted(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out"
            dest.mkdir()
            self.extract(archive_for("repo-root/tools/valid.txt"), dest)
            self.assertEqual((dest / "valid.txt").read_bytes(), b"ok")

    def test_parent_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out"
            dest.mkdir()
            payload = archive_for("repo-root/tools/../../outside.txt")
            with self.assertRaises(SystemExit):
                self.extract(payload, dest)
            self.assertFalse((Path(tmp) / "outside.txt").exists())

    def test_symlink_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "out"
            dest.mkdir()
            with self.assertRaises(SystemExit):
                self.extract(archive_for("repo-root/tools/link", kind="symlink"), dest)
            self.assertFalse((dest / "link").exists())
