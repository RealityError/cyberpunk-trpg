from pathlib import Path
from uuid import uuid4

import pytest

import characters
import sessions


@pytest.fixture
def storage_dir():
    path = Path(".tmp") / "tests" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def patch_storage(storage_dir):
    characters_file = storage_dir / "characters.json"
    sessions_file = storage_dir / "sessions.json"
    characters.CHARACTERS_FILE = characters_file
    sessions.CHARACTERS_FILE = characters_file
    sessions.SESSIONS_FILE = sessions_file
    return characters_file, sessions_file
