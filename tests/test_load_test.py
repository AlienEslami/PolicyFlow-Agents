import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_module(project_root: Path) -> ModuleType:
    path = project_root / "scripts" / "load_test.py"
    spec = importlib.util.spec_from_file_location("policyflow_load_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_nearest_rank_percentiles(project_root: Path) -> None:
    module = load_module(project_root)
    assert module.percentile([], 0.95) == 0.0
    assert module.percentile([5.0, 1.0, 3.0, 2.0, 4.0], 0.50) == 3.0
    assert module.percentile([5.0, 1.0, 3.0, 2.0, 4.0], 0.95) == 5.0
