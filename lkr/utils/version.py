import pathlib
import tomllib
import importlib.metadata

def get_version() -> str:
    try:
        return importlib.metadata.version("lkr")
    except importlib.metadata.PackageNotFoundError:
        try:
            pyproject_path = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    return data.get("project", {}).get("version", "unknown")
        except Exception:
            pass
        return "unknown"
