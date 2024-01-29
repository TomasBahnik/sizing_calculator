from __future__ import annotations

import os
import socket
import subprocess

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set

from loguru import logger


DATE_TIME_FORMAT_FOLDER = "%Y-%m-%dT%H-%M-%S%z"


def list_files(folder: Path, ends_with: str = ".txt", contains: Optional[str] = None) -> List[Path]:
    """
    traverse root directory, and list directories as dirs and files as files
    finds files or roots which contain `contains` string and ends_with `ends_with` string
    """
    file_type_files: List[Path] = []
    for root, dirs, files in os.walk(folder):
        for file in files:
            cond_ends = file.endswith(ends_with)
            cond_contains = True if contains is None else (contains in file or contains in root)
            condition = cond_ends and cond_contains
            if condition:
                l_f = Path(root, file)
                file_type_files.append(l_f)
    return file_type_files


def files_containing(files: List[Path] | Set[Path], contains: str):
    ret: List[Path] = []
    for file in files:
        #  for windows utf-8 explicitly
        f = open(file=file, encoding="utf-8", mode="r")
        if contains in f.read():
            ret.append(file)
        f.close()
    return ret


def time_stamp(date_time_format: str = DATE_TIME_FORMAT_FOLDER) -> str:
    """default format suitable for directory name"""
    return datetime.now(timezone.utc).strftime(date_time_format)


def archive_folder(src_path: Path, dest_path: Path, dest_base_file_name: str):
    """
    Create tar gz from 2nd to last dir of src_folder
    archive file name = dest_file_name + datatime stamp + suffix
    """
    dt = time_stamp()
    src_parts = src_path.parts
    last_folder = src_parts[-1]
    path_before_last_folder = Path(*src_parts[:-1])
    os.makedirs(dest_path, exist_ok=True)
    dest_file_name = Path(str(dest_base_file_name) + "-" + dt + ".tar.gz")
    full_archive_path: Path = Path(dest_path, dest_file_name).resolve()
    msg = f"Archive '{last_folder}' from {path_before_last_folder} to {full_archive_path}"
    logger.info(msg)
    # -C change dir to second to last backup dir and archive only this one
    cmd = [
        "tar",
        "-C",
        str(path_before_last_folder),
        "-czf",
        str(full_archive_path),
        last_folder,
    ]
    p = subprocess.run(cmd)
    return p


def check_folder(folder: Path) -> Path:
    if folder.exists() and folder.is_dir():
        return folder
    else:
        raise IsADirectoryError(folder)


def check_file(file: Path) -> Path:
    if file.exists() and file.is_file():
        return file
    else:
        raise FileNotFoundError(file)


def os_info():
    """OS and user info"""
    try:
        ret = f"OS:{os.name} host:{socket.gethostname()} user:{os.getlogin()}"
        return ret
    # On WSL os.getlogin() return FileNotFoundError: [Errno 2] No such file or directory
    except FileNotFoundError:
        return f"OS:{os.name} host:{socket.gethostname()}"


def find_chars_in_str(s: str, ch) -> List[int]:
    """
    Find positions of single char is string
    https://stackoverflow.com/questions/11122291/how-to-find-char-in-string-and-get-all-the-indexes
    :param s: string to search
    :param ch: char to search for
    :return: list of indexes of ch in s
    """
    return [i for i, ltr in enumerate(s) if ltr == ch]


def basic_auth(username: str, password: str) -> str:
    import base64

    auth = f"{username}:{password}"
    auth_bytes = auth.encode("utf-8")
    auth_b64 = base64.b64encode(auth_bytes)
    ret = f"Basic {auth_b64.decode('utf-8')}"
    return ret
