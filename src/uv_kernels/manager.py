import dataclasses
import os
import logging
import queue
import re
import sys
import typing as t
import tomllib
import threading

from jupyter_client.kernelspec import KernelSpec, KernelSpecManager
from traitlets import Bool

from pathlib import Path


_logger = logging.getLogger(__name__)

_MOCK = [
    Path("~/ryes/uvkernel1").expanduser(),
    Path("~/ryes/uvkernel2").expanduser(),
]

_BASE_DIRS = [Path("~/ryes").expanduser(), Path("~/proj").expanduser()]
_PREFIX = "uv_kernel_"
_PYPROJ = "pyproject.toml"

# everything starting with . as well
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
    try:
        with open(pyproject_file, "rb") as file:
            data = tomllib.load(file)
        deps = get_dotkey(data, "project.dependencies", [])
        print(pyproject_file.parent.name, deps)
        for dep in deps:
            if re.match(r"\bipykernel\b", dep) is not None:
                return True
        return False
    except (tomllib.TOMLDecodeError, OSError) as exc:
        _logger.error("Error when reading %r: %s", pyproject_file, exc)
        return False

def has_venv(pyproject_file: Path) -> bool:
    venv_dir = pyproject_file.parent / ".venv"
    return venv_dir.is_dir()


class ProjectScanner:
    def __init__(self):
        self.queue = queue.Queue()
        self.kernels = []
        self.started = False
        self._thread = None

    def start(self):
        if not self.started:
            self._thread = threading.Thread(target=self._scan)
            self._thread.start()
            self.started = True

    def _scan(self):
        print("started scan", file=sys.stderr)
        # run in thread
        for base_dir in _BASE_DIRS:
            for dirpath, dirnames, filenames in os.walk(base_dir):
                dirnames[:] = [n for n in dirnames if not n.startswith(".") and n not in _IGNORE_LIST]
                print(dirpath, dirnames, file=sys.stderr)
                if _PYPROJ in filenames:
                    pyproj_file = Path(dirpath) / _PYPROJ
                    if is_kernel_project(pyproj_file) and has_venv(pyproj_file):
                        print("Yes")
                        self.queue.put(UvKernel(pyproj_file))

    def is_done(self) -> bool:
        return False

    def get(self) -> list[UvKernel]:
        while not self.queue.empty():
            try:
                self.kernels.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return self.kernels


class UvKernelSpecManager(KernelSpecManager):
    """
    """
    use_uv_run = Bool(default_value=True).tag(config=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__scanner = ProjectScanner()

    def __uv_projects(self) -> list[UvKernel]:
        self.__scanner.start()
        return self.__scanner.get()

    def find_kernel_specs(self) -> dict[str, str]:
        ret = super().find_kernel_specs()
        uvs = self.__uv_projects()
        for uv in uvs:
            print("PROJECT:", uv)
        for k, v in ret.items():
            print(k, v)
        for mock in _MOCK:
            kernel_name = _PREFIX + str(mock.name)
            ret[kernel_name] = ""
        return ret

    def get_all_specs(self) -> dict[str, t.Any]:
        print("get_all_specs")
        ret = super().get_all_specs()
        for k, v in ret.items():
            print(k, v)
        return ret

    def get_kernel_spec(self, kernel_name: str) -> KernelSpec:
        if kernel_name.startswith(_PREFIX):
            props = _BASE_SPEC.copy()
            props.update(
                name=kernel_name,
                display_name=_MOCK[0].name
            )
            props["argv"][0] = str(_MOCK[0] / ".venv/bin/python")
            new_spec = KernelSpec(**props)
            print(new_spec.to_dict())
            return new_spec
        else:
            return super().get_kernel_spec(kernel_name)
