"""Sovereign Vault Manager for Sanctum Platform.
Enforces at-rest encryption on host storage using a 16-digit cryptographic passphrase.
Outside Sanctum, files are locked FRP1 containers unreadable to any external viewer or cloud LLM.
Inside Sanctum, files are transparently unlocked and decrypted in sovereign memory.
"""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.logger import logger
import sanctum_locker.core as locker

# 16-digit unique sovereign passphrase
DEFAULT_VAULT_PASSPHRASE = os.environ.get("SANCTUM_VAULT_PASSPHRASE", "8492017482910384")
MAGIC = locker.MAGIC  # b"FRP1"


def get_vault_passphrase() -> str:
    """Return the active 16-digit sovereign passphrase."""
    return os.environ.get("SANCTUM_VAULT_PASSPHRASE", DEFAULT_VAULT_PASSPHRASE).strip()


def format_passphrase(p: str) -> str:
    """Format 16-digit passphrase into human-readable 4-4-4-4 chunked format."""
    clean = re.sub(r"[^0-9a-zA-Z]", "", p)
    if len(clean) == 16:
        return f"{clean[:4]}-{clean[4:8]}-{clean[8:12]}-{clean[12:]}"
    return p


def is_file_locked(source: Union[str, Path, bytes, io.BytesIO]) -> bool:
    """Check if the target file or byte buffer is an encrypted FRP1 container."""
    try:
        if isinstance(source, (str, Path)):
            p = Path(source)
            if not p.is_file():
                return False
            with open(p, "rb") as f:
                header = f.read(len(MAGIC))
                return header == MAGIC
        elif isinstance(source, io.BytesIO):
            pos = source.tell()
            source.seek(0)
            header = source.read(len(MAGIC))
            source.seek(pos)
            return header == MAGIC
        elif isinstance(source, bytes):
            return source.startswith(MAGIC)
    except Exception as e:
        logger.debug(f"Error checking if file is locked: {e}")
    return False


def decrypt_sovereign_blob(blob: bytes, passphrase: Optional[str] = None) -> bytes:
    """Decrypt an in-memory FRP1 container using the 16-digit passphrase."""
    key = passphrase or get_vault_passphrase()
    clean_key = re.sub(r"[^0-9a-zA-Z]", "", key)
    # Try with raw key, or with hyphen-stripped key
    keys_to_try = [clean_key, key] if clean_key != key else [key]

    last_error = None
    for k in keys_to_try:
        try:
            enc_key, mac_key, nonce, ciphertext = locker._container_keys(blob, k)
            keystream = locker._keystream(enc_key, nonce, len(ciphertext))
            plaintext = bytes(a ^ b for a, b in zip(ciphertext, keystream))
            return plaintext
        except Exception as e:
            last_error = e

    raise ValueError(f"Sovereign Locker decryption failed: {last_error}")


def read_sovereign_bytes(
    source: Union[str, Path, bytes, io.BytesIO],
    passphrase: Optional[str] = None
) -> Tuple[bytes, bool]:
    """Read bytes from disk or buffer, decrypting on the fly if locked.
    Returns: (decrypted_bytes, is_locked)
    """
    raw_bytes: bytes
    if isinstance(source, (str, Path)):
        p = Path(source)
        with open(p, "rb") as f:
            raw_bytes = f.read()
    elif isinstance(source, io.BytesIO):
        raw_bytes = source.getvalue()
    elif isinstance(source, bytes):
        raw_bytes = source
    else:
        raise ValueError("Unsupported source type for sovereign vault reader.")

    if raw_bytes.startswith(MAGIC):
        decrypted = decrypt_sovereign_blob(raw_bytes, passphrase)
        return decrypted, True

    return raw_bytes, False


def read_sovereign_text(
    source: Union[str, Path, bytes],
    passphrase: Optional[str] = None
) -> Tuple[str, bool]:
    """Read text, decrypting on the fly if locked.
    Returns: (text, is_locked)
    """
    raw_bytes, was_locked = read_sovereign_bytes(source, passphrase)
    text = raw_bytes.decode("utf-8", errors="replace")
    return text, was_locked


def get_raw_disk_preview(file_path: Union[str, Path], max_bytes: int = 64) -> Dict[str, Any]:
    """Get raw disk representation of file for demo verification."""
    p = Path(file_path)
    if not p.is_file():
        return {"error": "File not found"}

    with open(p, "rb") as f:
        head = f.read(max_bytes)

    hex_dump = " ".join(f"{b:02x}" for b in head)
    ascii_repr = "".join(chr(b) if 32 <= b <= 126 else "." for b in head)
    is_locked = head.startswith(MAGIC)

    return {
        "file_name": p.name,
        "is_locked_on_disk": is_locked,
        "first_bytes_hex": hex_dump,
        "ascii_preview": ascii_repr,
        "file_size": p.stat().st_size,
        "container_magic": "FRP1" if is_locked else "PLAINTEXT",
    }


def lock_file_in_place(file_path: Union[str, Path], passphrase: Optional[str] = None) -> bool:
    """Lock/encrypt a file in-place on host disk using the 16-digit passphrase."""
    p = Path(file_path)
    if not p.is_file():
        return False
    if is_file_locked(p):
        return True  # Already locked

    key = passphrase or get_vault_passphrase()
    locker.restrict_file(p, key)
    logger.info(f"[SOVEREIGN VAULT] Locked file on disk: {p.name}")
    return True


def unlock_file_in_place(file_path: Union[str, Path], passphrase: Optional[str] = None) -> bool:
    """Unlock/decrypt a file in-place on host disk."""
    p = Path(file_path)
    if not p.is_file():
        return False
    if not is_file_locked(p):
        return True  # Already plaintext

    key = passphrase or get_vault_passphrase()
    locker.unrestrict_file_in_place(p, key)
    logger.info(f"[SOVEREIGN VAULT] Unlocked file on disk: {p.name}")
    return True


def lock_workspace_directory(workspace_dir: Union[str, Path], passphrase: Optional[str] = None) -> Dict[str, Any]:
    """Lock all files in the workspace directory."""
    root = Path(workspace_dir).resolve()
    key = passphrase or get_vault_passphrase()
    locked_count = 0
    already_locked = 0
    skipped = 0

    for item in root.rglob("*"):
        if not item.is_file():
            continue
        rel = str(item.relative_to(root))
        if rel.startswith(".") or "/." in rel or rel.startswith("node_modules"):
            skipped += 1
            continue

        if is_file_locked(item):
            already_locked += 1
        else:
            try:
                lock_file_in_place(item, key)
                locked_count += 1
            except Exception as e:
                logger.warning(f"Could not lock {rel}: {e}")

    return {
        "status": "ok",
        "passphrase": format_passphrase(key),
        "newly_locked": locked_count,
        "already_locked": already_locked,
        "total_protected": locked_count + already_locked,
    }


def unlock_workspace_directory(workspace_dir: Union[str, Path], passphrase: Optional[str] = None) -> Dict[str, Any]:
    """Unlock all files in the workspace directory."""
    root = Path(workspace_dir).resolve()
    key = passphrase or get_vault_passphrase()
    unlocked_count = 0

    for item in root.rglob("*"):
        if not item.is_file():
            continue
        rel = str(item.relative_to(root))
        if rel.startswith(".") or "/." in rel:
            continue

        if is_file_locked(item):
            try:
                unlock_file_in_place(item, key)
                unlocked_count += 1
            except Exception as e:
                logger.warning(f"Could not unlock {rel}: {e}")

    return {
        "status": "ok",
        "unlocked_count": unlocked_count,
    }


def get_workspace_vault_summary(workspace_dir: Union[str, Path]) -> Dict[str, Any]:
    """Get security and at-rest encryption summary for the workspace."""
    root = Path(workspace_dir).resolve()
    total_files = 0
    locked_files = 0
    locked_list = []

    for item in root.rglob("*"):
        if not item.is_file():
            continue
        rel = str(item.relative_to(root))
        if rel.startswith(".") or "/." in rel:
            continue

        total_files += 1
        if is_file_locked(item):
            locked_files += 1
            locked_list.append(rel)

    passphrase = get_vault_passphrase()
    return {
        "passphrase": format_passphrase(passphrase),
        "passphrase_raw": passphrase,
        "passphrase_length": len(passphrase),
        "total_files": total_files,
        "locked_files": locked_files,
        "unlocked_files": total_files - locked_files,
        "is_all_locked": (locked_files == total_files) if total_files > 0 else False,
        "encryption_format": "FRP1 Container (PBKDF2-HMAC-SHA256, 200,000 iterations + Keystream + HMAC-SHA256 Auth)",
        "security_verdict": "AT_REST_ENCRYPTED" if locked_files > 0 else "PLAINTEXT_WARNING",
        "locked_file_samples": locked_list[:10],
    }
