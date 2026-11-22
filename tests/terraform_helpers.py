"""
Helpers for tests that run Terraform step by step: plan, read the plan's
apply graph, and apply a saved plan.
"""

import json
import os
import re
import time
from os import path as osp
from shutil import rmtree
from subprocess import PIPE, STDOUT, CompletedProcess, run
from textwrap import dedent
from typing import Dict, Iterable, List, Optional, Set, Tuple, Union

from infrahouse_core.timeout import timeout

from tests.conftest import LOG

# An edge in `terraform graph` output: "A" -> "B" means A waits for B.
EDGE_PATTERN = re.compile(r'^\s*"\[root\] (?P<src>[^"]+)" -> "\[root\] (?P<dst>[^"]+)"')

TfvarValue = Optional[Union[str, Dict[str, str]]]


def reset_terraform_dir(terraform_dir: str, generated: Iterable[str] = ()) -> None:
    """
    Remove what an earlier run left in a test root, so the run starts clean.

    State files stay: ``terraform destroy`` from an earlier run needs them.

    :param terraform_dir: Path to the test root module.
    :param generated: Names of other files the test writes into the root.
    """
    for name in (".terraform", ".terraform.lock.hcl", *generated):
        file_path = osp.join(terraform_dir, name)
        if osp.isdir(file_path):
            rmtree(file_path)
        elif osp.isfile(file_path):
            os.remove(file_path)


def write_terraform_tf(terraform_dir: str, aws_provider_version: str) -> None:
    """
    Write ``terraform.tf`` that pins the AWS provider version.

    :param terraform_dir: Path to the test root module.
    :param aws_provider_version: AWS provider version constraint.
    """
    with open(osp.join(terraform_dir, "terraform.tf"), "w", encoding="utf-8") as fp:
        fp.write(dedent(f"""\
                terraform {{
                  required_providers {{
                    aws = {{
                      source  = "hashicorp/aws"
                      version = "{aws_provider_version}"
                    }}
                  }}
                }}
                """))


def write_tfvars(terraform_dir: str, tfvars: Dict[str, TfvarValue]) -> None:
    """
    Write ``terraform.tfvars``; ``None`` values are left out.

    An HCL value accepts JSON syntax, so each value is written as JSON.

    :param terraform_dir: Path to the test root module.
    :param tfvars: Variable names and values.
    """
    with open(osp.join(terraform_dir, "terraform.tfvars"), "w", encoding="utf-8") as fp:
        for name, value in tfvars.items():
            if value is not None:
                fp.write(f"{name} = {json.dumps(value)}\n")
    # The pre-commit hook runs terraform fmt -check -recursive, which also
    # reads generated files.
    terraform(terraform_dir, "fmt", "terraform.tfvars")


def terraform(terraform_dir: str, *args: str, check: bool = True) -> CompletedProcess:
    """
    Run a terraform subcommand, log its output and return the result.

    :param terraform_dir: Path to the test root module.
    :param args: Terraform subcommand and its arguments.
    :param check: Raise if terraform exits with non-zero.
    :return: The finished process; ``stdout`` holds stdout and stderr together.
    :raise CalledProcessError: If ``check`` is true and terraform exits with non-zero.
    """
    LOG.info("terraform %s", " ".join(args))
    result = run(
        ["terraform", *args],
        cwd=terraform_dir,
        stdout=PIPE,
        stderr=STDOUT,
        text=True,
        check=False,
    )
    LOG.info("%s", result.stdout)
    if check:
        result.check_returncode()
    return result


def plan_to_file(terraform_dir: str, plan_file: str) -> int:
    """
    Save a plan and return ``terraform plan -detailed-exitcode``'s status.

    :param terraform_dir: Path to the test root module.
    :param plan_file: Where to save the plan.
    :return: 0 if the plan has no changes, 2 if it has.
    :raise AssertionError: If the plan fails.
    """
    result = terraform(
        terraform_dir,
        "plan",
        "-var-file=terraform.tfvars",
        "-input=false",
        "-no-color",
        "-detailed-exitcode",
        f"-out={plan_file}",
        check=False,
    )
    assert result.returncode in (0, 2), f"terraform plan failed:\n{result.stdout}"
    return result.returncode


def graph_edges(terraform_dir: str, plan_file: str) -> Set[Tuple[str, str]]:
    """
    Read the apply graph of a saved plan.

    :param terraform_dir: Path to the test root module.
    :param plan_file: The saved plan.
    :return: Edges ``(a, b)``: node ``a`` waits for node ``b``. Node names are
        as ``terraform graph`` prints them, without the ``[root]`` prefix,
        e.g. ``module.bucket.aws_iam_role.replication[0] (destroy)``.
    """
    dot = run(
        ["terraform", "graph", f"-plan={plan_file}"],
        cwd=terraform_dir,
        stdout=PIPE,
        text=True,
        check=True,
    ).stdout
    edges = set()
    for line in dot.splitlines():
        match = EDGE_PATTERN.match(line)
        if match:
            edges.add((match.group("src"), match.group("dst")))
    return edges


def log_edges(edges: Set[Tuple[str, str]], substrings: Iterable[str]) -> None:
    """
    Log the edges between nodes whose names contain one of ``substrings``.

    :param edges: Edges from :func:`graph_edges`.
    :param substrings: Parts of node names to keep, e.g. ``"aws_iam_role"``.
    """
    substrings = tuple(substrings)
    kept = sorted(
        (src, dst)
        for src, dst in edges
        if any(s in src for s in substrings) and any(s in dst for s in substrings)
    )
    LOG.info(
        "Graph edges (A -> B: A waits for B):\n%s",
        "\n".join(f'"{src}" -> "{dst}"' for src, dst in kept),
    )


def waits_for(edges: Set[Tuple[str, str]], node: str, dependency: str) -> bool:
    """
    Tell whether ``node`` waits for ``dependency``, directly or through other nodes.

    :param edges: Edges from :func:`graph_edges`.
    :param node: Name of the node that would wait.
    :param dependency: Name of the node it would wait for.
    :return: True if a path of edges leads from ``node`` to ``dependency``.
    """
    successors: Dict[str, List[str]] = {}
    for src, dst in edges:
        successors.setdefault(src, []).append(dst)
    seen = set()
    stack = [node]
    while stack:
        current = stack.pop()
        for nxt in successors.get(current, []):
            if nxt == dependency:
                return True
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


def state_addresses(terraform_dir: str) -> List[str]:
    """
    List the addresses in the root's state.

    :param terraform_dir: Path to the test root module.
    :return: Output of ``terraform state list``, one address per item.
    """
    return terraform(terraform_dir, "state", "list").stdout.split()


def wait_for_replication(s3_replica, replica_bucket: str, key: str) -> None:
    """
    Poll the replica bucket until ``key`` appears.

    :param s3_replica: boto3 S3 client in the replica's region.
    :param replica_bucket: Replica bucket name.
    :param key: Object key to wait for.
    :raise TimeoutError: If the object doesn't appear within 5 minutes.
    """
    with timeout(300):
        while True:
            time.sleep(10)
            try:
                s3_replica.get_object(Bucket=replica_bucket, Key=key)
                LOG.info("Object %s replicated to %s", key, replica_bucket)
                return
            except s3_replica.exceptions.NoSuchKey:
                LOG.info("Object %s not yet replicated, retrying...", key)
