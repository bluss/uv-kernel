import dataclasses
import os
import logging
import queue
import re
import typing as t
import tomllib
import threading

from jupyter_client.kernelspec import KernelSpec, KernelSpecManager
from traitlets import Bool, List

from pathlib import Path


_logger = logging.getLogger(__name__)


_PREFIX = "uv_kernel_"
_PYPROJ = "pyproject.toml"
_SAFETY_LIMIT = 50

# ignore directories with '.' prefix and anything in this set
_IGNORE_LIST = {"node_modules"}

_BASE_SPEC = {
    "argv": ["python", "-m", "ipykernel_launcher", "-f", "{connection_file}"],
    "env": {},
    "display_name": "ipykernel",
    "language": "python",
    "interrupt_mode": "signal",
    "metadata": {"debugger": True},
}


@dataclasses.dataclass
class UvKernel:
    # pyproject file
    project: Path

    def directory(self) -> Path:
        return self.project.parent

    def kernel_name(self) -> str:
        home = Path("~").expanduser()
        try:
            path = self.directory().relative_to(home)
        except ValueError:
            path = self.directory()
        return _PREFIX + "_".join(path.parts)

    def display_name(self) -> str:
        return "/".join(self.directory().parts[-2:])

    def python_path(self) -> str:
        return str(get_venv_bin_python(self.directory() / ".venv"))


def get_venv_bin_python(base_venv: Path) -> Path:
    is_windows = os.name == "nt"
    script_dir = "Scripts" if is_windows else "bin"
    extension = ".exe" if is_windows else ""
    return base_venv / script_dir / Path("python").with_suffix(extension)


def get_dotkey(data: dict, dotkey, default):
    parts = dotkey.split(".")
    root = data
    for part in parts:
        try:
            root = root[part]
        except KeyError:
            return default
    return root


def is_kernel_project(pyproject_file: Path) -> bool:
    """
    True if has ipykernel
    """
    _logger.debug("Scanning file %r", pyproject_file)
    try:
        with open(pyproject_file, "rb") as file:
            data = tomllib.load(file)
        deps = get_dotkey(data, "project.dependencies", [])
        for dep in deps:
            if re.match(r"\bipykernel\b", dep) is not None:
                return True
        return False
    except (tomllib.TOMLDecodeError, OSError) as exc:
        _logger.error("Error when reading %r: %s", pyproject_file, exc)
        return False


def has_venv(pyproject_file: Path) -> bool:
    venv_python = get_venv_bin_python(pyproject_file.parent / ".venv")
    return venv_python.is_file()


class ProjectScanner:
    def __init__(self, base_directories: list[str]):
        self.queue = queue.Queue()
        self.kernels = []
        self.started = False
        self.base_directories = base_directories
        self._thread = None

    def start(self):
        if not self.started:
            self._thread = threading.Thread(target=self._scan)
            self._thread.start()
            self.started = True

    def _scan(self):
        # run in thread
        _logger.debug("%s: started scan", type(self).__name__)
        for base_dir in self.base_directories:
            dir = Path(base_dir).expanduser()
            if not dir.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(dir):
                dirnames[:] = [n for n in dirnames if not n.startswith(".") and n not in _IGNORE_LIST]
                if _PYPROJ in filenames:
                    pyproj_file = Path(dirpath) / _PYPROJ
                    if is_kernel_project(pyproj_file) and has_venv(pyproj_file):
                        self.queue.put(UvKernel(pyproj_file))

    def is_done(self) -> bool:
        return False

    def get(self) -> list[UvKernel]:
        while not self.queue.empty():
            try:
                self.kernels.append(self.queue.get_nowait())
                _logger.info("Found uv = %r", self.kernels[-1])
            except queue.Empty:
                break
        return self.kernels


class UvKernelSpecManager(KernelSpecManager):
    """
    KernelSpecManager that finds installed kernel specs,
    and also scans for uv projects with ipykernel - in given base directories
    """
    use_uv_run = Bool(default_value=False).tag(config=True)
    base_directories = List[str](default_value=["~"]).tag(config=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        _logger.info("Base directories: %r", self.base_directories)
        self.__scanner = ProjectScanner(self.base_directories)

    def __uv_projects(self) -> list[UvKernel]:
        self.__scanner.start()
        projects = self.__scanner.get()
        return projects[:_SAFETY_LIMIT]

    def find_kernel_specs(self) -> dict[str, str]:
        ret = super().find_kernel_specs()
        uvs = self.__uv_projects()
        for uv in uvs:
            kernel_name = uv.kernel_name()
            ret[kernel_name] = ""
        return ret

    def get_all_specs(self) -> dict[str, t.Any]:
        ret = super().get_all_specs()
        return ret

    def get_kernel_spec(self, kernel_name: str) -> KernelSpec:
        if kernel_name.startswith(_PREFIX):
            uvs = self.__uv_projects()
            for uv in uvs:
                if kernel_name == uv.kernel_name():
                    break
            else:
                raise ValueError(f"No such project {kernel_name}")
            props = _BASE_SPEC.copy()
            props.update(
                name=kernel_name,
                display_name=uv.display_name(),
            )
            argv = props["argv"]
            if self.use_uv_run:
                # uv run --directory
                argv = ["uv", "run", "--directory", str(uv.directory())] + argv
            else:
                # ./path/to/python
                argv[0] = uv.python_path()
            props["argv"] = argv
            new_spec = KernelSpec(**props)
            _logger.info("Kernel Spec %r", new_spec.to_dict())
            return new_spec
        else:
            return super().get_kernel_spec(kernel_name)
