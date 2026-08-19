import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.filesystem import get_file_info, list_directory, read_text_file, find_files, search_text
from core.models import FileInfo, TextReadResult

def test_file_info():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"hello world")
        tmp_path = tmp.name
    try:
        info = get_file_info(tmp_path)
        assert isinstance(info, FileInfo)
        assert info.exists is True
        assert info.is_file is True
        assert info.is_directory is False
        assert info.name == os.path.basename(tmp_path)
        assert info.size_bytes == 11
        assert info.extension is None  # no extension -> None
        # modified_at should be a datetime
        assert info.modified_at is not None
        assert isinstance(info.modified_at, datetime)
    finally:
        os.unlink(tmp_path)

def test_directory_info():
    with tempfile.TemporaryDirectory() as tmpdir:
        # create a file inside
        sub = Path(tmpdir) / "test.txt"
        sub.write_text("test")
        info = get_file_info(tmpdir)
        assert info.exists is True
        assert info.is_directory is True
        assert info.is_file is False
        listing = list_directory(tmpdir)
        assert isinstance(listing, list)
        # should have at least our file
        assert any(f.name == "test.txt" and f.is_file for f in listing)
        # also check that we got FileInfo objects
        for f in listing:
            assert isinstance(f, FileInfo)

def test_nonexistent_path():
    info = get_file_info("__this_path_does_not_exist_12345__")
    assert info.exists is False
    assert info.is_file is False
    assert info.is_directory is False

def test_text_reading():
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp:
        tmp.write(b"Hello\nWorld!")
        tmp_path = tmp.name
    try:
        result = read_text_file(tmp_path)
        assert isinstance(result, TextReadResult)
        assert result.success is True
        assert result.content == "Hello\nWorld!"
        assert result.encoding == 'utf-8'
        assert result.truncated is False
        assert result.size_bytes == len(b"Hello\nWorld!")
        assert result.error == "" or result.error is None
    finally:
        os.unlink(tmp_path)

def test_truncation():
    # create a file larger than default max_bytes (1MB is huge, so we'll set a small max_bytes for test)
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp:
        tmp.write(b"A" * 2000)
        tmp_path = tmp.name
    try:
        result = read_text_file(tmp_path, max_bytes=100)
        assert result.success is True
        assert result.truncated is True
        assert len(result.content) == 100
        assert result.size_bytes == 2000
    finally:
        os.unlink(tmp_path)

def test_file_search():
    with tempfile.TemporaryDirectory() as tmpdir:
        # create some files
        (Path(tmpdir) / "config.yaml").write_text("{}")
        (Path(tmpdir) / "example.json").write_text("[]")
        (Path(tmpdir) / "service.log").write_text("log")
        (Path(tmpdir) / "other.txt").write_text("txt")
        # find *.yaml
        yaml_files = find_files(tmpdir, "*.yaml", recursive=True)
        assert len(yaml_files) == 1
        assert yaml_files[0].name == "config.yaml"
        assert yaml_files[0].extension == ".yaml"
        # find * (all files) with limit
        all_files = find_files(tmpdir, "*", recursive=True, max_results=2)
        assert len(all_files) <= 2
        # recursive vs non-recursive
        non_rec = find_files(tmpdir, "*", recursive=False, max_results=1000)
        # non-recursive should not find files in subdirs (there are none) but should find the immediate files
        # Actually, the files are directly in tmpdir, so both should find them.
        # We'll just ensure the function works.
        assert isinstance(non_rec, list)

def test_text_search():
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp:
        tmp.write(b"line one\nExecution here\nline three")
        tmp_path = tmp.name
    try:
        matches = search_text(tmp_path, "execution", case_insensitive=True)
        assert len(matches) == 1
        assert matches[0]['line_number'] == 2
        assert "Execution" in matches[0]['line']
        # case sensitive
        matches2 = search_text(tmp_path, b"Execution".decode(), case_insensitive=False)
        assert len(matches2) == 1
        # not found if case sensitive and wrong case
        matches3 = search_text(tmp_path, "execution", case_insensitive=False)
        assert len(matches3) == 0
    finally:
        os.unlink(tmp_path)

def test_binary_handling():
    with tempfile.NamedTemporaryFile(delete=False, mode='wb') as tmp:
        tmp.write(b'\x00\x01\x02\x03')  # binary with null
        tmp_path = tmp.name
    try:
        result = read_text_file(tmp_path)
        # Should fail to decode due to null byte
        assert result.success is False
        assert result.error != ""
        assert result.content == ""
        assert result.encoding is None
    finally:
        os.unlink(tmp_path)

def test_result_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(10):
            (Path(tmpdir) / f"file{i}.txt").write_text(f"content {i}")
        # ask for max 3
        files = find_files(tmpdir, "*.txt", recursive=True, max_results=3)
        assert len(files) == 3
        # search_text limit
        matches = search_text(tmpdir, "content", recursive=True, max_results=2)
        assert len(matches) == 2

def test_datetime_regression():
    """Regression test: get_file_info must populate modified_at as a datetime and not raise NameError."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"test")
        tmp_path = tmp.name
    try:
        info = get_file_info(tmp_path)
        assert info.exists is True
        assert info.modified_at is not None
        assert isinstance(info.modified_at, datetime)
    finally:
        os.unlink(tmp_path)

def test_exclude_dirs():
    with tempfile.TemporaryDirectory() as tmpdir:
        # create a directory structure
        root = Path(tmpdir)
        (root / "keep.txt").write_text("keep")
        (root / ".venv").mkdir()
        (root / ".venv" / "ignore.txt").write_text("ignore")
        (root / "__pycache__").mkdir()
        (root / "__pycache__" / "junk.txt").write_text("junk")
        (root / "sub").mkdir()
        (root / "sub" / "ok.txt").write_text("ok")
        # find all txt files, excluding .venv and __pycache__
        files = find_files(tmpdir, "*.txt", recursive=True, exclude_dirs={".venv", "__pycache__"})
        names = {f.name for f in files}
        assert "keep.txt" in names
        assert "ok.txt" in names
        assert "ignore.txt" not in names
        assert "junk.txt" not in names
        # search_text should also respect excludes
        matches = search_text(tmpdir, "keep", recursive=True, exclude_dirs={".venv", "__pycache__"})
        assert len(matches) == 1
        assert matches[0]['path'].endswith("keep.txt")
        # a search inside an excluded dir should not find it
        matches2 = search_text(tmpdir, "ignore", recursive=True, exclude_dirs={".venv", "__pycache__"})
        assert len(matches2) == 0

if __name__ == "__main__":
    import traceback
    tests = [
        test_file_info,
        test_directory_info,
        test_nonexistent_path,
        test_text_reading,
        test_truncation,
        test_file_search,
        test_text_search,
        test_binary_handling,
        test_result_limit,
        test_datetime_regression,
        test_exclude_dirs,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"PASS: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL: {test.__name__}")
            traceback.print_exc()
    print(f"\nTotal: {passed} passed, {failed} failed")
    sys.exit(1 if failed > 0 else 0)
