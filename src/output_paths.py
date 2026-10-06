"""Fresh output directories: refuse replacement and never delete prior evidence."""
from pathlib import Path


def fresh_directory(path: str | Path) -> Path:
    path = Path(path)
    if path.is_symlink():
        raise FileExistsError(f"refusing symlink output: {path}")
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise FileExistsError(f"refusing nonempty output: {path}")
    else:
        path.mkdir(parents=True)
    return path


def write_text_exclusive(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
