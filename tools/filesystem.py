import os
import sys
import stat
from pathlib import Path
from typing import List, Optional, Iterator, Set
from core.models import FileInfo, TextReadResult
from core.logging_config import setup_logging
from datetime import datetime

logger = setup_logging("ev.filesystem")

def get_file_info(path: str) -> FileInfo:
    """
    Get information about a file or directory.
    Returns a FileInfo model.
    Does not raise exceptions for inaccessible paths; instead, sets exists=False and other fields to defaults/None.
    """
    p = Path(path)
    info = FileInfo(
        path=str(p.resolve()) if p.exists() else path,
        name=p.name,
        exists=False,
        is_file=False,
        is_directory=False,
        size_bytes=None,
        modified_at=None,
        extension=None,
    )
    try:
        if p.exists():
            info.exists = True
            if p.is_file():
                info.is_file = True
            elif p.is_dir():
                info.is_directory = True
            else:
                # Other types (symlink, etc.) - we treat as not file/dir for simplicity
                pass
            stat_info = p.stat()
            info.size_bytes = stat_info.st_size
            info.modified_at = datetime.fromtimestamp(stat_info.st_mtime)
            if p.is_file():
                info.extension = p.suffix.lower() if p.suffix else None
    except (PermissionError, OSError) as e:
        logger.warning("Unable to get info for %s: %s", path, e)
        # Leave exists as False if we cannot stat? Actually we know it exists because we checked p.exists()
        # But if stat fails, we still know it exists but can't get details.
        # We'll set exists=True but leave other fields as None/default.
        info.exists = True
        # Keep other fields as they were (size_bytes=None, etc.)
    return info

def list_directory(path: str) -> List[FileInfo]:
    """
    List the contents of a directory.
    Returns a list of FileInfo for each entry.
    Does not recurse.
    Skips entries that cannot be accessed.
    """
    p = Path(path)
    if not p.exists() or not p.is_dir():
        logger.warning("Path %s does not exist or is not a directory", path)
        return []
    entries: List[FileInfo] = []
    try:
        for item in p.iterdir():
            try:
                info = get_file_info(str(item))
                entries.append(info)
            except Exception as e:
                logger.warning("Skipping entry %s: %s", item, e)
                continue
    except (PermissionError, OSError) as e:
        logger.error("Error listing directory %s: %s", path, e)
    return entries

def read_text_file(path: str, max_bytes: int = 1024 * 1024) -> TextReadResult:
    """
    Read a text file up to max_bytes bytes.
    Returns a TextReadResult.
    Tries to decode as UTF-8, then falls back to the system's default encoding if UTF-8 fails.
    If the file is binary (or not decodable), returns success=False with an error message.
    We consider a file binary if it contains a null byte (0x00) in the sampled data.
    """
    p = Path(path)
    result = TextReadResult(
        path=str(p),
        success=False,
        content="",
        encoding=None,
        truncated=False,
        size_bytes=None,
        error="",
    )
    if not p.exists() or not p.is_file():
        result.error = "File does not exist or is not a file"
        return result
    try:
        size = p.stat().st_size
        result.size_bytes = size
        if size > max_bytes:
            result.truncated = True
            # Read only up to max_bytes
            with p.open('rb') as f:
                raw = f.read(max_bytes)
        else:
            with p.open('rb') as f:
                raw = f.read()
        # Binary detection: null byte in the sampled data
        if b'\x00' in raw:
            result.error = "Binary file detected (null byte)"
            return result
        # Try to decode
        try:
            result.content = raw.decode('utf-8')
            result.encoding = 'utf-8'
        except UnicodeDecodeError:
            # Fallback to system default encoding (may still fail)
            try:
                result.content = raw.decode(sys.getdefaultencoding())
                result.encoding = sys.getdefaultencoding()
            except UnicodeDecodeError:
                result.error = "File appears to be binary or not decodable as text"
                return result
        result.success = True
    except (PermissionError, OSError) as e:
        result.error = f"Unable to read file: {e}"
        logger.error("Error reading file %s: %s", path, e)
    return result

def find_files(root: str, pattern: str, recursive: bool = True, max_results: int = 200, exclude_dirs: Optional[Set[str]] = None) -> List[FileInfo]:
    """
    Find files matching a pattern under a root directory.
    Uses glob (recursive: '**' if recursive else '*').
    Returns up to max_results FileInfo objects.
    exclude_dirs: a set of directory names to skip (e.g., {'.venv', '__pycache__'})
    """
    if exclude_dirs is None:
        exclude_dirs = set()
    p = Path(root)
    if not p.exists() or not p.is_dir():
        logger.warning("Root path %s does not exist or is not a directory", root)
        return []
    # Use rglob for recursive, glob for non-recursive
    if recursive:
        iterator = p.rglob(pattern)
    else:
        iterator = p.glob(pattern)
    results: List[FileInfo] = []
    count = 0
    for item in iterator:
        # Skip if any parent directory is in exclude_dirs
        if any(part in exclude_dirs for part in item.parts):
            continue
        if count >= max_results:
            logger.warning("Reached max_results limit (%d) for find_files", max_results)
            break
        if item.is_file():
            try:
                info = get_file_info(str(item))
                results.append(info)
                count += 1
            except Exception as e:
                logger.warning("Skipping file %s: %s", item, e)
                continue
    return results

def search_text(root_or_file: str, text: str, recursive: bool = True, max_results: int = 200, case_insensitive: bool = True, exclude_dirs: Optional[Set[str]] = None) -> List[dict]:
    """
    Search for text in files under a root or in a single file.
    Returns a list of dictionaries with keys: path, line_number, line (snippet).
    Skips files that cannot be read as text.
    exclude_dirs: a set of directory names to skip (e.g., {'.venv', '__pycache__'})
    """
    if exclude_dirs is None:
        exclude_dirs = set()
    matches: List[dict] = []
    if case_insensitive:
        text_to_find = text.lower()
    else:
        text_to_find = text
    # Determine if root_or_file is a file or directory
    p = Path(root_or_file)
    if p.is_file():
        files_to_search = [p]
    elif p.is_dir():
        if recursive:
            files_to_search = list(p.rglob('*'))
        else:
            files_to_search = list(p.glob('*'))
        # Filter to only files
        files_to_search = [f for f in files_to_search if f.is_file()]
        # Exclude files in excluded directories
        files_to_search = [f for f in files_to_search if not any(part in exclude_dirs for part in f.parts)]
    else:
        logger.warning("Path %s does not exist", root_or_file)
        return matches
    for file_path in files_to_search:
        if len(matches) >= max_results:
            logger.warning("Reached max_results limit (%d) for search_text", max_results)
            break
        try:
            read_result = read_text_file(str(file_path))
            if not read_result.success:
                # Skip unreadable/binary files
                continue
            lines = read_result.content.splitlines()
            for i, line in enumerate(lines, start=1):
                line_to_check = line.lower() if case_insensitive else line
                if text_to_find in line_to_check:
                    # Return a snippet (the whole line, but we could limit length)
                    matches.append({
                        "path": str(file_path),
                        "line_number": i,
                        "line": line.rstrip('\r\n')
                    })
                    if len(matches) >= max_results:
                        break
        except Exception as e:
            logger.warning("Error searching in %s: %s", file_path, e)
            continue
    return matches
