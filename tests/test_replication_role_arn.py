"""
Tests for replication_role_arn (issue #34).

With replication_role_arn set, the module replicates with the caller's IAM
role and creates no role of its own. A deployment that moves from the
module's role to its own must have replication updated before the module's
role and policy are deleted, so replication never points at a deleted role.
"""

import json
import re
from os import path as osp
from subprocess import CalledProcessError
from typing import Dict, List, Optional, Set

import pytest
from boto3 import Session
from pytest_infrahouse import terraform_apply

from tests.conftest import LOG, TERRAFORM_ROOT_DIR
from tests.terraform_helpers import (
    graph_edges,
    log_edges,
    plan_json,
    plan_to_file,
    reset_terraform_dir,
    state_addresses,
    terraform,
    wait_for_replication,
    waits_for,
    write_terraform_tf,
    write_tfvars,
)

ROOT_DIR = osp.join(TERRAFORM_ROOT_DIR, "test_replication_role_arn")
INVALID_INPUTS_DIR = osp.join(TERRAFORM_ROOT_DIR, "test_invalid_inputs")
BUCKET_TF = "bucket.tf"
PLAN_FILE = "tfplan"

UPGRADE_FROM_VERSION = "0.9.0"
REGISTRY_SOURCE = f'source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"\n  version = "{UPGRADE_FROM_VERSION}"'
LOCAL_SOURCE = 'source = "../../"'

MODULE_ROLE = "module.bucket.aws_iam_role.replication[0]"
MODULE_POLICY = "module.bucket.aws_iam_role_policy.replication[0]"
REPLICATION = "module.bucket.aws_s3_bucket_replication_configuration.this[0]"

# Everything the module creates for its own role. None of it may be in the
# state when the caller passes replication_role_arn.
MODULE_ROLE_RESOURCES = {
    "module.bucket.aws_iam_role.replication",
    "module.bucket.aws_iam_role_policy.replication",
    "module.bucket.data.aws_iam_policy_document.replication_assume_role",
    "module.bucket.data.aws_iam_policy_document.replication_policy",
}

# The caller's role, created in the same apply as the module. Built as a
# string, the ARN is known not to be null at plan time, which the module's
# count needs.
CALLER_ROLE_ARN_TEMPLATE = (
    '"arn:${data.aws_partition.current.partition}:iam::'
    '${data.aws_caller_identity.current.account_id}:role/${aws_iam_role.caller.name}"'
)
# The caller's role once it is in the state: its ARN is known at plan time.
CALLER_ROLE_ARN_REFERENCE = "aws_iam_role.caller.arn"


@pytest.mark.parametrize("aws_provider_version", ["~> 6.0"], ids=["aws-6"])
def test_replication_role_arn(
    boto3_session: Session,
    test_role_arn: str,
    keep_after: bool,
    aws_region: str,
    aws_provider_version: str,
) -> None:
    """
    Replicate with a role the caller creates in the same apply.

    The module must create no IAM role, policy or policy document, the
    replication configuration must use the caller's role, and an object put
    into the source bucket must reach the replica.
    """
    replica_region = _prepare_root(aws_region, test_role_arn, aws_provider_version)
    _write_bucket_tf(LOCAL_SOURCE, CALLER_ROLE_ARN_TEMPLATE)

    with terraform_apply(
        ROOT_DIR,
        destroy_after=not keep_after,
        json_output=True,
    ) as tf_output:
        _assert_no_module_role(state_addresses(ROOT_DIR))
        _assert_replicates_with(
            boto3_session,
            aws_region,
            replica_region,
            tf_output,
            "test-replication-role-arn.txt",
        )


@pytest.mark.parametrize("aws_provider_version", ["~> 6.0"], ids=["aws-6"])
def test_switch_to_replication_role_arn(
    boto3_session: Session,
    test_role_arn: str,
    keep_after: bool,
    aws_region: str,
    aws_provider_version: str,
) -> None:
    """
    Move a deployment from the module's replication role to the caller's.

    1. Apply 0.9.0 from the registry. The module creates its own role; the
       caller's role exists next to it.
    2. Plan the switch to replication_role_arn in the same apply as the
       upgrade from 0.9.0, and log the order the graph gives. Not applied.
    3. Upgrade to this checkout without replication_role_arn. The plan must
       not create, delete or replace anything; the only in-place changes it
       may have are tags (#32 tags the replication role). Apply it: that
       records create_before_destroy for the module's role and policy in
       the state.
    4. Set replication_role_arn. From the plan's graph and the apply log,
       replication must be updated before the module's role and policy are
       deleted. Then replication must work with the caller's role.

    Start from a clean account: with ``--keep-after``, the next run would
    apply 0.9.0 on top of the switched state.
    """
    replica_region = _prepare_root(aws_region, test_role_arn, aws_provider_version)
    _write_bucket_tf(REGISTRY_SOURCE)

    with terraform_apply(
        ROOT_DIR,
        destroy_after=not keep_after,
        json_output=True,
    ) as tf_output:
        role_before = _replication_role(boto3_session, aws_region, tf_output)
        assert role_before != tf_output["caller_role_arn"]["value"]
        LOG.info(
            "%s replicates with the module's role %s", UPGRADE_FROM_VERSION, role_before
        )

        # Step 2: switch in the same apply as the upgrade.
        _switch_source(LOCAL_SOURCE, CALLER_ROLE_ARN_REFERENCE)
        assert plan_to_file(ROOT_DIR, PLAN_FILE) == 2
        edges = graph_edges(ROOT_DIR, PLAN_FILE)
        log_edges(edges, ("aws_iam_role", "replication_configuration"))
        LOG.info(
            "Switching in the same apply as the upgrade from %s: replication "
            "update waits for the role delete: %s; role delete waits for the "
            "replication update: %s",
            UPGRADE_FROM_VERSION,
            waits_for(edges, REPLICATION, f"{MODULE_ROLE} (destroy)"),
            waits_for(edges, f"{MODULE_ROLE} (destroy)", REPLICATION),
        )

        # Step 3: upgrade without replication_role_arn.
        _write_bucket_tf(LOCAL_SOURCE)
        plan_to_file(ROOT_DIR, PLAN_FILE)
        _assert_only_tag_updates(plan_json(ROOT_DIR, PLAN_FILE))
        terraform(ROOT_DIR, "apply", "-input=false", "-no-color", PLAN_FILE)
        _log_create_before_destroy()

        # Step 4: switch to the caller's role.
        _write_bucket_tf(LOCAL_SOURCE, CALLER_ROLE_ARN_REFERENCE)
        assert plan_to_file(ROOT_DIR, PLAN_FILE) == 2
        edges = graph_edges(ROOT_DIR, PLAN_FILE)
        log_edges(edges, ("aws_iam_role", "replication_configuration"))
        for deleted in (MODULE_ROLE, MODULE_POLICY):
            assert waits_for(
                edges, f"{deleted} (destroy)", REPLICATION
            ), f"The delete of {deleted} doesn't wait for the replication update"
        assert not waits_for(
            edges, REPLICATION, f"{MODULE_ROLE} (destroy)"
        ), "The replication update waits for the module's role to be deleted"

        apply_log = terraform(
            ROOT_DIR, "apply", "-input=false", "-no-color", PLAN_FILE
        ).stdout.splitlines()
        updated = _line_index(apply_log, f"{REPLICATION}: Modifications complete")
        for deleted in (MODULE_ROLE, MODULE_POLICY):
            assert updated < _line_index(
                apply_log, f"{deleted}: Destroying..."
            ), f"{deleted} was deleted before the replication update completed"

        _assert_no_module_role(state_addresses(ROOT_DIR))
        _assert_replicates_with(
            boto3_session,
            aws_region,
            replica_region,
            tf_output,
            "test-switch-to-replication-role-arn.txt",
        )


@pytest.mark.parametrize("aws_provider_version", ["~> 6.0"], ids=["aws-6"])
@pytest.mark.parametrize(
    "inputs, expected_error",
    [
        (
            {
                "replication_region": "us-west-1",
                "replication_role_arn": "s3-replication",
            },
            "replication_role_arn must be an IAM role ARN",
        ),
        (
            {
                "replication_role_arn": "arn:aws:iam::{account_id}:role/s3-replication",
                "vanta_exemptions": {
                    "aws-s3-cross-region-replication-enabled": "Plan-only test"
                },
            },
            "replication_role_arn is set, but replication_region is null",
        ),
    ],
    ids=["not-an-arn", "no-replication-region"],
)
def test_replication_role_arn_rejected(
    boto3_session: Session,
    test_role_arn: str,
    aws_region: str,
    aws_provider_version: str,
    inputs: Dict,
    expected_error: str,
) -> None:
    """
    The plan must fail for a role name instead of an ARN, and for a role
    without replication_region. Creates nothing.
    """
    account_id = boto3_session.client("sts").get_caller_identity()["Account"]
    tfvars = {"region": aws_region, "role_arn": test_role_arn}
    for name, value in inputs.items():
        tfvars[name] = (
            value.format(account_id=account_id) if isinstance(value, str) else value
        )

    reset_terraform_dir(INVALID_INPUTS_DIR)
    write_terraform_tf(INVALID_INPUTS_DIR, aws_provider_version)
    write_tfvars(INVALID_INPUTS_DIR, tfvars)
    terraform(INVALID_INPUTS_DIR, "init", "-no-color")
    result = terraform(
        INVALID_INPUTS_DIR,
        "plan",
        "-var-file=terraform.tfvars",
        "-input=false",
        "-no-color",
        check=False,
    )
    assert result.returncode != 0, "The plan must fail"
    # Terraform wraps long messages; compare with whitespace collapsed.
    assert expected_error in " ".join(result.stdout.split())


def _prepare_root(
    aws_region: str, test_role_arn: Optional[str], aws_provider_version: str
) -> str:
    """
    Reset the test root and write its terraform.tf and terraform.tfvars.

    :param aws_region: Region of the source bucket.
    :param test_role_arn: Role for Terraform to assume, if any.
    :param aws_provider_version: AWS provider version constraint.
    :return: Region of the replica bucket.
    """
    # Replication needs a destination region different from the source.
    replica_region = "us-east-1" if aws_region == "us-west-1" else "us-west-1"
    reset_terraform_dir(ROOT_DIR, (BUCKET_TF, PLAN_FILE))
    write_terraform_tf(ROOT_DIR, aws_provider_version)
    write_tfvars(
        ROOT_DIR,
        {
            "region": aws_region,
            "role_arn": test_role_arn,
            "replication_region": replica_region,
        },
    )
    return replica_region


def _write_bucket_tf(source: str, replication_role_arn: Optional[str] = None) -> None:
    """
    Write the module block.

    :param source: The ``source`` (and ``version``) lines of the module block.
    :param replication_role_arn: Expression for replication_role_arn, or None
        to leave it out (0.9.0 has no such input).
    """
    lines = [
        'module "bucket" {',
        f"  {source}",
        '  bucket_prefix      = "role-arn"',
        "  force_destroy      = true",
        "  replication_region = var.replication_region",
    ]
    if replication_role_arn is not None:
        lines.append(f"  replication_role_arn = {replication_role_arn}")
    lines.append("}")
    with open(osp.join(ROOT_DIR, BUCKET_TF), "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    # The pre-commit hook runs terraform fmt -check -recursive, which also
    # reads this generated file.
    terraform(ROOT_DIR, "fmt", BUCKET_TF)


def _switch_source(source: str, replication_role_arn: Optional[str]) -> None:
    """
    Point the module block at another source and re-initialize the root.

    If ``terraform init`` fails, restore the registry source so the
    ``terraform destroy`` in ``terraform_apply`` can still run.

    :param source: The ``source`` (and ``version``) lines of the module block.
    :param replication_role_arn: Expression for replication_role_arn, or None.
    """
    _write_bucket_tf(source, replication_role_arn)
    try:
        terraform(ROOT_DIR, "init", "-no-color")
    except CalledProcessError:
        _write_bucket_tf(REGISTRY_SOURCE)
        raise


def _replication_role(boto3_session: Session, aws_region: str, tf_output: Dict) -> str:
    """
    Read the role the source bucket replicates with.

    :param boto3_session: Session with the test role.
    :param aws_region: Region of the source bucket.
    :param tf_output: ``terraform output`` of the test root.
    :return: The replication configuration's role ARN.
    """
    s3_source = boto3_session.client("s3", region_name=aws_region)
    return s3_source.get_bucket_replication(Bucket=tf_output["bucket_name"]["value"])[
        "ReplicationConfiguration"
    ]["Role"]


def _assert_no_module_role(addresses: List[str]) -> None:
    """
    Fail if the state has the module's role, policy or their policy documents.

    :param addresses: Output of ``terraform state list``.
    """
    created = [
        address
        for address in addresses
        if re.sub(r"\[[^]]*]$", "", address) in MODULE_ROLE_RESOURCES
    ]
    assert (
        not created
    ), f"The module created its own role with replication_role_arn set: {created}"


def _assert_replicates_with(
    boto3_session: Session,
    aws_region: str,
    replica_region: str,
    tf_output: Dict,
    key: str,
) -> None:
    """
    Check that replication uses the caller's role and an object reaches the replica.

    :param boto3_session: Session with the test role.
    :param aws_region: Region of the source bucket.
    :param replica_region: Region of the replica bucket.
    :param tf_output: ``terraform output`` of the test root, read after the
        apply that created the buckets.
    :param key: Key of the object to put into the source bucket.
    """
    caller_role_arn = tf_output["caller_role_arn"]["value"]
    role = _replication_role(boto3_session, aws_region, tf_output)
    assert (
        role == caller_role_arn
    ), f"Replication uses {role}, expected {caller_role_arn}"

    s3_source = boto3_session.client("s3", region_name=aws_region)
    s3_source.put_object(
        Bucket=tf_output["bucket_name"]["value"],
        Key=key,
        Body=b"replicated with the caller's role",
    )
    wait_for_replication(
        boto3_session.client("s3", region_name=replica_region),
        tf_output["replica_bucket_name"]["value"],
        key,
    )


def _assert_only_tag_updates(plan: Dict) -> None:
    """
    Fail unless every managed resource change in the plan is a no-op or an
    in-place update of tags.

    :param plan: Output of ``terraform show -json`` for the saved plan.
    """
    problems = []
    for change in plan.get("resource_changes", []):
        if change["mode"] != "managed":
            continue
        actions = change["change"]["actions"]
        if actions == ["no-op"]:
            continue
        if actions != ["update"]:
            problems.append(f"{change['address']}: {actions}")
            continue
        changed = _changed_attributes(change["change"])
        LOG.info("%s updates in place: %s", change["address"], sorted(changed))
        if not changed <= {"tags", "tags_all"}:
            problems.append(f"{change['address']}: updates {sorted(changed)}")
    assert not problems, (
        f"Upgrading from {UPGRADE_FROM_VERSION} without replication_role_arn may "
        "only update tags in place:\n" + "\n".join(problems)
    )


def _changed_attributes(change: Dict) -> Set[str]:
    """
    Name the top-level attributes an update changes.

    :param change: The ``change`` object of a resource change in plan JSON.
    :return: Attributes whose value differs, or is unknown after the update.
    """
    before = change.get("before") or {}
    after = change.get("after") or {}
    unknown = change.get("after_unknown") or {}
    return {
        key
        for key in set(before) | set(after) | set(unknown)
        if before.get(key) != after.get(key) or unknown.get(key)
    }


def _line_index(lines: List[str], prefix: str) -> int:
    """
    Find the first line that starts with ``prefix``.

    :param lines: Lines of terraform output.
    :param prefix: Start of the line to find.
    :return: Index of the line.
    :raise AssertionError: If no line starts with ``prefix``.
    """
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            return index
    raise AssertionError(f"No line starts with {prefix!r}")


def _log_create_before_destroy() -> None:
    """
    Log which module resources have create_before_destroy in the state.
    """
    with open(osp.join(ROOT_DIR, "terraform.tfstate"), encoding="utf-8") as fp:
        state = json.load(fp)
    flags = {
        f"{resource.get('module', '')}.{resource['type']}.{resource['name']}": [
            instance.get("create_before_destroy", False)
            for instance in resource["instances"]
        ]
        for resource in state["resources"]
        if resource["mode"] == "managed"
    }
    LOG.info("create_before_destroy in the state: %s", json.dumps(flags, indent=4))
