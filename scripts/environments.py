"""
The environments a repository deploys to, one YAML file each.

Each file of ``environments`` is an environment, named after it
(``environments/prod.yml`` is ``prod``), and says everything that tells it
apart from the others: its workspace, the branch that deploys to it, the
value set of its variable libraries, the parameters of its semantic models
and the orphans a deployment leaves in place. So the pipelines hold no
environment of their own: they ask which environment a branch deploys to.

Run as a script, it answers the pipelines without pyfabricops::

    python environments.py --branch main     # prints prod, or nothing
    python environments.py --list            # a JSON list for a matrix
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# The YAML file of each environment, in the environments folder at the root
# of the repository, one folder above this script.
ENVIRONMENTS = Path(__file__).resolve().parents[1] / "environments"
SUFFIX = ".yml"
KEYS = {
    "workspace",
    "branch",
    "gitConnected",
    "valueSet",
    "parameters",
    "keep",
}
# Lowercase letters, digits and "-": the same name for the file, the
# environment of GitHub or Azure DevOps and --environment, on any system.
NAME = re.compile(r"[a-z0-9][a-z0-9-]*")
# What makes a branch of an environment a glob, such as release/*.
GLOB = re.compile(r"[*?\[]")


@dataclass(frozen=True)
class Environment:
    """An environment, as its file in ``environments`` describes it."""

    name: str
    file: Path
    workspace: str
    # The branch that deploys to it, as a name or a glob such as release/*.
    branch: str | None
    # Whether its workspace is connected to Git, whose IDs the items hold.
    git_connected: bool
    # The value set made active in each variable library, if any.
    value_set: str | None
    # The parameter values of each semantic model, as the file gives them.
    parameters: Mapping[str, Mapping[str, str]]
    # The names of the orphans --allow-deletions leaves in the workspace.
    keep: tuple[re.Pattern[str], ...] = ()

    def keeps(self, name: str) -> bool:
        """Whether an orphan of this name stays in the workspace."""
        return any(pattern.fullmatch(name) for pattern in self.keep)

    def deploys(self, branch: str) -> bool:
        """Whether a branch deploys to this environment."""
        return self.branch is not None and fnmatch.fnmatchcase(
            branch, self.branch
        )


def _text(value: Any) -> bool:
    """Whether a YAML value is a non-empty string."""
    return isinstance(value, str) and bool(value)


def _parameters(
    file: Path, raw: Any
) -> tuple[dict[str, dict[str, str]], list[str]]:
    """
    The parameters of each model, and what is wrong with them.

    Every name and value must be text: YAML reads 5432 as a number, and
    yes or on as true, which would reach the model as another text than
    the one written.
    """
    if not isinstance(raw, dict):
        return {}, [f"{file.name}: parameters is not a mapping."]
    parameters: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    for model, values in raw.items():
        if not isinstance(values, dict):
            problems.append(
                f"{file.name}: parameters of {model} is not a mapping."
            )
            continue
        for name, value in values.items():
            if not isinstance(name, str):
                problems.append(
                    f"{file.name}: a parameter of {model} is named "
                    f"{name!r}, not text; quote it."
                )
            elif not isinstance(value, str):
                problems.append(
                    f"{file.name}: parameter {name} of {model} is "
                    f"{value!r}, not text; quote it."
                )
        parameters[str(model)] = {str(k): str(v) for k, v in values.items()}
    return parameters, problems


def read_environment(name: str) -> Environment:
    """The environment of a name; exits when its file is missing or wrong."""
    file = ENVIRONMENTS / f"{name}{SUFFIX}"
    if not file.is_file():
        known = ", ".join(names())
        raise SystemExit(
            f"No environment {name}: {file} is missing. Known: {known}."
        )
    content = yaml.safe_load(file.read_text(encoding="utf-8-sig")) or {}
    if not isinstance(content, dict):
        raise SystemExit(f"{file.name}: not a mapping of keys.")
    problems = [
        f"{file.name}: unknown key {key}."
        for key in sorted(set(map(str, content)) - KEYS)
    ]
    if not NAME.fullmatch(name):
        problems.append(
            f"{file.name}: name an environment with lowercase letters, "
            "digits and '-'."
        )
    workspace = content.get("workspace")
    branch = content.get("branch")
    git_connected = content.get("gitConnected", False)
    value_set = content.get("valueSet")
    keep = content.get("keep", [])
    if not _text(workspace):
        problems.append(f"{file.name}: no workspace.")
    if branch is not None and not _text(branch):
        problems.append(f"{file.name}: branch is not a name.")
    if not isinstance(git_connected, bool):
        problems.append(f"{file.name}: gitConnected is not true or false.")
    elif git_connected:
        problems += [
            f"{file.name}: {key}, but it is connected to Git, and no run "
            "deploys to it."
            for key in ("valueSet", "parameters", "keep")
            if key in content
        ]
    if value_set is not None and not _text(value_set):
        problems.append(f"{file.name}: valueSet is not a name.")
    parameters, wrong = _parameters(file, content.get("parameters", {}))
    problems += wrong
    patterns: list[re.Pattern[str]] = []
    if not isinstance(keep, list):
        problems.append(f"{file.name}: keep is not a list of names.")
    else:
        for entry in keep:
            try:
                patterns.append(re.compile(str(entry)))
            except re.error as error:
                problems.append(f"{file.name}: keep {entry!r}: {error}.")
    if problems:
        raise SystemExit("\n".join(problems))
    return Environment(
        name=name,
        file=file,
        workspace=str(workspace),
        branch=branch,
        git_connected=git_connected,
        value_set=value_set,
        parameters=parameters,
        keep=tuple(patterns),
    )


def names() -> list[str]:
    """The names of the environments, from their files."""
    return sorted(path.stem for path in ENVIRONMENTS.glob(f"*{SUFFIX}"))


def read_all() -> list[Environment]:
    """
    Every environment; exits when one is wrong, or when they do not fit
    together: one at most connected to Git, and no branch that deploys to
    two of them.
    """
    environments = [read_environment(name) for name in names()]
    connected = [e.name for e in environments if e.git_connected]
    problems: list[str] = []
    if len(connected) > 1:
        problems.append(
            "One environment at most is connected to Git, not "
            f"{', '.join(connected)}."
        )
    branches: dict[str, str] = {}
    for environment in environments:
        if environment.branch is None:
            continue
        other = branches.setdefault(environment.branch, environment.name)
        if other != environment.name:
            problems.append(
                f"Branch {environment.branch} deploys to both {other} and "
                f"{environment.name}."
            )
    if problems:
        raise SystemExit("\n".join(problems))
    return environments


def git_environment() -> Environment | None:
    """The environment connected to Git, whose IDs the items hold, if any."""
    return next((e for e in read_all() if e.git_connected), None)


def for_branch(branch: str) -> Environment | None:
    """
    The environment a branch deploys to, or None.

    A ref such as refs/heads/main, as Azure DevOps gives it, is read as its
    branch. A branch matching two globs, such as release/* and release/1.*,
    exits rather than pick one.
    """
    branch = branch.removeprefix("refs/heads/")
    found = [e for e in read_all() if e.deploys(branch)]
    if len(found) > 1:
        raise SystemExit(
            f"Branch {branch} deploys to "
            f"{', '.join(e.name for e in found)}; make one branch match one "
            "environment."
        )
    return found[0] if found else None


def main(argv: Sequence[str] | None = None) -> int:
    """Answer the pipelines: the environment of a branch, or the list."""
    parser = argparse.ArgumentParser(
        description="Tell which environment a branch deploys to."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--branch",
        help="Print the environment this branch deploys to, or nothing.",
    )
    mode.add_argument(
        "--list",
        action="store_true",
        help="Print the environments a run deploys to from one branch, as a "
        'JSON list of {"name", "branch"} for the matrix of a job: not the '
        "one connected to Git, which no run deploys to, nor one whose branch "
        "is a glob, which names no branch to check out.",
    )
    args = parser.parse_args(argv)
    if args.list:
        print(
            json.dumps(
                [
                    {"name": e.name, "branch": e.branch}
                    for e in read_all()
                    if e.branch is not None
                    and not e.git_connected
                    and not GLOB.search(e.branch)
                ]
            )
        )
        return 0
    environment = for_branch(args.branch)
    print(environment.name if environment else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
