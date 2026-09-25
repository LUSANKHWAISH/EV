import hashlib
import os
import shutil
import stat
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional, Set, Union

from core.logging_config import setup_logging
from core.models import FileDeleteResult, FileInfo, FileWriteResult, TextReadResult

logger = setup_logging("ev.filesystem")

DEFAULT_ALLOWED_ROOTS = [
    Path(r"D:\EV\workspace"),
    Path(r"D:\EV\sandbox"),
    Path(r"D:\EV\backups"),
    Path(r"D:\EV\test_runtime"),
]

# DOS reserved device names
DOS_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def validate_sandbox_path(
    path: Union[str, Path],
    allowed_roots: Optional[List[Union[str, Path]]] = None,
) -> Path:
    """
    Validate and return the canonical Path within an allowed sandbox root.
    Raises ValueError or PermissionError if invalid or outside sandbox.
    """
    if path is None or not isinstance(path, (str, Path)):
        raise ValueError("Path must be a non-empty string or Path object")

    raw_path_str = str(path).strip().strip('"').strip("'")
    if not raw_path_str:
        raise ValueError("Path cannot be empty")

    if "\x00" in raw_path_str:
        raise ValueError("Path contains invalid null byte")

    # Reject UNC network paths
    if raw_path_str.startswith(r"\\") or raw_path_str.startswith("//"):
        raise PermissionError("UNC network paths are not allowed in sandbox")

    p = Path(raw_path_str)

    # Check for reserved DOS device names
    stem_upper = p.stem.upper()
    if stem_upper in DOS_DEVICE_NAMES:
        raise PermissionError(f"Reserved DOS device name '{stem_upper}' is not allowed")

    # Check for alternate data streams (colons beyond drive specifier)
    parts_str = str(p)
    if len(parts_str) >= 2 and parts_str[1] == ":":
        rest = parts_str[2:]
        if ":" in rest:
            raise PermissionError("Alternate Data Streams are not allowed")
    elif ":" in parts_str:
        raise PermissionError("Alternate Data Streams are not allowed")

    try:
        resolved = p.resolve()
    except Exception as exc:
        raise PermissionError(f"Unable to resolve path: {exc}")

    roots = [Path(r).resolve() for r in (allowed_roots or DEFAULT_ALLOWED_ROOTS)]

    # Check if resolved path is within any allowed root
    is_allowed = False
    for root in roots:
        try:
            if resolved.is_relative_to(root) or resolved == root:
                is_allowed = True
                break
        except AttributeError:
            try:
                resolved.relative_to(root)
                is_allowed = True
                break
            except ValueError:
                pass

    if not is_allowed:
        raise PermissionError(
            f"Path '{resolved}' is outside allowed sandbox roots: {[str(r) for r in roots]}"
        )

    return resolved


def write_file(
    path: str,
    content: str,
    encoding: str = "utf-8",
    overwrite: bool = True,
    allowed_roots: Optional[List[Union[str, Path]]] = None,
) -> FileWriteResult:
    """
    Write content to a file in the sandbox.
    Returns FileWriteResult.
    """
    try:
        validated_path = validate_sandbox_path(path, allowed_roots=allowed_roots)
    except Exception as exc:
        return FileWriteResult(
            path=str(path),
            success=False,
            bytes_written=0,
            created=False,
            error=f"SandboxValidationError: {exc}",
        )

    if not isinstance(content, str):
        return FileWriteResult(
            path=str(validated_path),
            success=False,
            bytes_written=0,
            created=False,
            error="TypeError: Content must be a string",
        )

    # Max 1 MB content limit
    if len(content) > 1024 * 1024:
        return FileWriteResult(
            path=str(validated_path),
            success=False,
            bytes_written=0,
            created=False,
            error="ValueError: Content exceeds maximum limit of 1 MB",
        )

    try:
        encoded_bytes = content.encode(encoding)
    except Exception as exc:
        return FileWriteResult(
            path=str(validated_path),
            success=False,
            bytes_written=0,
            created=False,
            error=f"EncodingError: Failed to encode content using {encoding}: {exc}",
        )

    file_existed = validated_path.exists()
    if file_existed and not overwrite:
        return FileWriteResult(
            path=str(validated_path),
            success=False,
            bytes_written=0,
            created=False,
            error="FileExistsError: Target file already exists and overwrite is False",
        )

    try:
        validated_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write via temporary file in the same directory
        parent_dir = validated_path.parent
        fd, temp_file_path = tempfile.mkstemp(
            suffix=validated_path.suffix, dir=parent_dir, prefix=".ev_tmp_"
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(encoded_bytes)
            # Atomic rename / replace
            os.replace(temp_file_path, validated_path)
        finally:
            if os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass

        # Calculate sha256 of written file
        h = hashlib.sha256(encoded_bytes).hexdigest()
        return FileWriteResult(
            path=str(validated_path),
            success=True,
            bytes_written=len(encoded_bytes),
            created=not file_existed,
            sha256=h,
            error=None,
        )
    except Exception as exc:
        logger.exception("Error writing file %s: %s", validated_path, exc)
        return FileWriteResult(
            path=str(validated_path),
            success=False,
            bytes_written=0,
            created=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def delete_file(
    path: str,
    missing_ok: bool = False,
    allowed_roots: Optional[List[Union[str, Path]]] = None,
) -> FileDeleteResult:
    """
    Delete a file in the sandbox.
    Returns FileDeleteResult.
    """
    try:
        validated_path = validate_sandbox_path(path, allowed_roots=allowed_roots)
    except Exception as exc:
        return FileDeleteResult(
            path=str(path),
            success=False,
            deleted=False,
            error=f"SandboxValidationError: {exc}",
        )

    if not validated_path.exists():
        if missing_ok:
            return FileDeleteResult(
                path=str(validated_path),
                success=True,
                deleted=False,
                error=None,
            )
        return FileDeleteResult(
            path=str(validated_path),
            success=False,
            deleted=False,
            error="FileNotFoundError: File does not exist",
        )

    if validated_path.is_dir():
        return FileDeleteResult(
            path=str(validated_path),
            success=False,
            deleted=False,
            error="IsADirectoryError: Target is a directory, not a regular file",
        )

    try:
        validated_path.unlink()
        return FileDeleteResult(
            path=str(validated_path),
            success=True,
            deleted=True,
            error=None,
        )
    except Exception as exc:
        logger.exception("Error deleting file %s: %s", validated_path, exc)
        return FileDeleteResult(
            path=str(validated_path),
            success=False,
            deleted=False,
            error=f"{type(exc).__name__}: {exc}",
        )


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
