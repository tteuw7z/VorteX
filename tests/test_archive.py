import argparse
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import BadZipFile, ZIP_BZIP2, ZIP_DEFLATED, ZIP_LZMA, ZIP_STORED, ZipFile, ZipInfo

from vortex.archive import discover_videos, extract_archive, inventory, repack_archive
from vortex.archive_cli import add_commands


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.archive = self.root / "source.zip"
        self.output = self.root / "unpacked"

    def make_archive(self, entries, compression=ZIP_STORED):
        with ZipFile(self.archive, "w", compression) as archive:
            archive.comment = b"archive comment"
            for name, contents in entries:
                archive.writestr(name, contents)

    def test_extract_and_repack_preserve_unicode_paths_and_bytes(self):
        entries = [
            ("pasta/edição.txt", b"old"),
            ("pasta/dados", bytes(range(256))),
            ("pasta/", b""),
            ("vazia/", b""),
        ]
        self.make_archive(entries, ZIP_DEFLATED)
        before = self.archive.read_bytes()
        self.assertEqual(inventory(self.archive)[0],
                         {"path": "pasta/edição.txt", "size": 3, "directory": False})

        extracted = extract_archive(self.archive, self.output)
        self.assertEqual((extracted.files, extracted.directories, extracted.bytes_written),
                         (2, 2, 259))
        self.assertTrue((self.output / "vazia").is_dir())
        self.assertEqual((self.output / "pasta/dados").read_bytes(), entries[1][1])
        replacement = self.output / "pasta/edição.txt"
        replacement.write_text("edição ✅", encoding="utf-8")

        output_zip = self.root / "edited.zip"
        repacked = repack_archive(self.archive, output_zip, {"pasta/edição.txt": replacement})
        self.assertEqual(repacked.files, 2)
        self.assertEqual(repacked.replaced, ("pasta/edição.txt",))
        self.assertEqual(self.archive.read_bytes(), before)
        with ZipFile(output_zip) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.comment, b"archive comment")
            self.assertEqual(archive.namelist(), [name for name, _ in entries])
            self.assertEqual(archive.read("pasta/dados"), entries[1][1])
            self.assertEqual(archive.read("pasta/edição.txt"), replacement.read_bytes())

    def test_all_paths_are_checked_before_output(self):
        invalid = (
            "../fora.txt", "/folder.txt", "vol:path", "sub\\member", ".//file", "x//y.txt",
            "x/./y.txt", "NUL.txt", "com¹.aux", "D/CLOCK$.log", "part./good", "part /good",
            "embedded?mark", "linha\n.txt",
        )
        for name in invalid:
            with self.subTest(name=name):
                self.make_archive([("first.txt", b"valid"), (name, b"invalid")])
                with self.assertRaises(ValueError):
                    extract_archive(self.archive, self.output)
                self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.iterdir()), [self.archive])

    def test_conflicting_ancestors_and_normalization(self):
        for names in (
            ("dir/a.txt", "DIR/b.txt"),
            ("dir", "dir/file"),
            ("dir/file", "dir"),
            ("dir/", "dir"),
            ("café.txt", "cafe\u0301.txt"),
        ):
            with self.subTest(names=names):
                self.make_archive([(first, b"" if first.endswith("/") else b"1") for first in names])
                with self.assertRaises(ValueError):
                    inventory(self.archive)

    def test_special_files_are_rejected(self):
        for file_type in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR):
            with self.subTest(file_type=file_type):
                info = ZipInfo("special")
                info.create_system = 3
                info.external_attr = (file_type | 0o600) << 16
                self.make_archive([(info, b"fixture")])
                with self.assertRaises(ValueError):
                    extract_archive(self.archive, self.output)
                self.assertFalse(self.output.exists())

    def test_overwrite_rejected_and_during_publication(self):
        self.make_archive([("file.txt", b"data")])
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            extract_archive(self.archive, self.output)
        self.assertEqual(list(self.output.iterdir()), [])

        self.output.rmdir()
        from vortex.archive import _publish

        def reserve_name_first(staged, destination):
            destination.mkdir()
            _publish(staged, destination)

        with patch("vortex.archive._publish", side_effect=reserve_name_first):
            with self.assertRaises(FileExistsError):
                extract_archive(self.archive, self.output)
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertFalse(list(self.root.glob(".vortex-zip-*")))

    def test_crc_failure_preserves_destinations_and_inputs(self):
        self.make_archive([("valid.txt", b"good"), ("broken.txt", b"original-late")])
        damaged = self.archive.read_bytes().replace(b"original-late", b"modified-late")
        self.archive.write_bytes(damaged)
        with self.assertRaises(BadZipFile):
            extract_archive(self.archive, self.output)
        self.assertFalse(self.output.exists())

        edit = self.root / "replacement"
        edit.write_bytes(b"corrected")
        new = self.root / "new.zip"
        with self.assertRaises(BadZipFile):
            repack_archive(self.archive, new, {"broken.txt": edit})
        self.assertFalse(new.exists())
        self.assertEqual(self.archive.read_bytes(), damaged)
        self.assertFalse(list(self.root.glob(".vortex-zip-*")))

    def test_budget_includes_implicit_directories_and_replacement(self):
        self.make_archive([("a/b/file", b"1234")])
        self.assertEqual(len(inventory(self.archive, max_entries=1, max_bytes=4)), 1)
        for bounds in ({"max_entries": 2}, {"max_bytes": 3}):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                extract_archive(self.archive, self.output, **bounds)
        self.assertFalse(self.output.exists())

        replacement = self.root / "replacement"
        replacement.write_bytes(b"12345")
        new = self.root / "new.zip"
        with self.assertRaises(ValueError):
            repack_archive(self.archive, new, {"a/b/file": replacement}, max_bytes=4)
        self.assertFalse(new.exists())

    def test_repack_rejects_unknown_member_and_existing_output(self):
        self.make_archive([("file.txt", b"contents")])
        edit = self.root / "replacement"
        edit.write_bytes(b"new")
        with self.assertRaises(ValueError):
            repack_archive(self.archive, self.output, {"unknown.txt": edit})
        self.assertFalse(self.output.exists())
        before = self.archive.read_bytes()
        with self.assertRaises(FileExistsError):
            repack_archive(self.archive, self.archive, {"file.txt": edit})
        self.assertEqual(self.archive.read_bytes(), before)

    def test_zip_and_directory_discover_all_17_candidates(self):
        paths = [f"vídeos/aula{number:02}.MP4" for number in range(17)]
        data = [(path, f"candidate {i}".encode()) for i, path in enumerate(paths)]
        self.make_archive([("readme.txt", b"notes"), ("pasta.mp4/", b""), *reversed(data)])
        candidates = discover_videos(self.archive)
        self.assertEqual([member["path"] for member in candidates], paths)
        extract_archive(self.archive, self.output)
        self.assertEqual(discover_videos(self.output), candidates)
        with self.assertRaises(ValueError):
            discover_videos(self.output, max_entries=16)

    def test_supported_codecs_and_unsafe_memory_codec(self):
        self.make_archive([("video.mp4", b"payload")], ZIP_BZIP2)
        extract_archive(self.archive, self.output)
        self.assertEqual((self.output / "video.mp4").read_bytes(), b"payload")
        self.make_archive([("video.mp4", b"payload")], ZIP_LZMA)
        self.assertEqual(len(inventory(self.archive)), 1)
        new = self.root / "new"
        with self.assertRaisesRegex(ValueError, "Unsupported compression"):
            extract_archive(self.archive, new)
        self.assertFalse(new.exists())

    def test_archive_commands(self):
        self.make_archive([("folder/test.txt", b"initial")])
        parser = argparse.ArgumentParser()
        add_commands(parser.add_subparsers())
        args = parser.parse_args(["archive", "extract", str(self.archive), str(self.output)])
        self.assertEqual(args.technical_handler(args)["files"], 1)
        edited = self.output / "folder/test.txt"
        edited.write_text("new")
        args = parser.parse_args(["archive", "repack", str(self.archive), str(self.root / "out.zip"),
                                  "--replace", "folder/test.txt", str(edited)])
        self.assertEqual(args.technical_handler(args)["replaced"], ["folder/test.txt"])
