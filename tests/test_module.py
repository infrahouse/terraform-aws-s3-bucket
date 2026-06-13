import json
import time
from os import path as osp, remove
from shutil import rmtree
from textwrap import dedent

import botocore.exceptions
import pytest
from infrahouse_core.timeout import timeout
from pytest_infrahouse import terraform_apply

from tests.conftest import (
    LOG,
    TERRAFORM_ROOT_DIR,
)


@pytest.mark.parametrize("aws_provider_version", ["~> 6.0"], ids=["aws-6"])
def test_module(
    boto3_session,
    test_role_arn,
    keep_after,
    aws_region,
    aws_provider_version,
):
    terraform_dir = osp.join(TERRAFORM_ROOT_DIR, "test_module")
    state_files = [
        osp.join(terraform_dir, ".terraform"),
        osp.join(terraform_dir, ".terraform.lock.hcl"),
    ]

    for state_file in state_files:
        try:
            if osp.isdir(state_file):
                rmtree(state_file)
            elif osp.isfile(state_file):
                remove(state_file)
        except FileNotFoundError:
            pass

    # Write terraform.tf with the specific AWS provider version
    with open(osp.join(terraform_dir, "terraform.tf"), "w") as fp:
        fp.write(dedent(f"""
                terraform {{
                  required_providers {{
                    aws = {{
                      source  = "hashicorp/aws"
                      version = "{aws_provider_version}"
                    }}
                  }}
                }}
                """))

    # Write terraform.tfvars
    with open(osp.join(terraform_dir, "terraform.tfvars"), "w") as fp:
        fp.write(dedent(f"""
                region          = "{aws_region}"
                """))
        if test_role_arn:
            fp.write(dedent(f"""
                    role_arn      = "{test_role_arn}"
                    """))

    with terraform_apply(
        terraform_dir,
        destroy_after=not keep_after,
        json_output=True,
    ) as tf_output:
        LOG.info(json.dumps(tf_output, indent=4))

        source_bucket = tf_output["bucket_name"]["value"]
        replica_bucket = tf_output["replica_bucket_name"]["value"]

        assert replica_bucket is not None
        assert "-replica" in replica_bucket

        # bucket_name_with_policy is sourced from the policy resource but must
        # be a drop-in equivalent of bucket_name for callers.
        assert tf_output["bucket_name_with_policy"]["value"] == source_bucket

        s3_source = boto3_session.client("s3", region_name=aws_region)
        s3_replica = boto3_session.client("s3", region_name="us-west-1")

        # Put an object in the source bucket
        test_key = "test-replication-object.txt"
        test_body = b"replication test content"
        s3_source.put_object(
            Bucket=source_bucket,
            Key=test_key,
            Body=test_body,
        )
        LOG.info("Put object %s in source bucket %s", test_key, source_bucket)

        # Poll the replica bucket until the object appears
        with timeout(300):
            while True:
                time.sleep(10)
                try:
                    response = s3_replica.get_object(
                        Bucket=replica_bucket,
                        Key=test_key,
                    )
                    LOG.info(
                        "Object replicated. Storage class: %s",
                        response.get("StorageClass", "STANDARD"),
                    )
                    break
                except s3_replica.exceptions.NoSuchKey:
                    LOG.info("Object not yet replicated, retrying...")

        # Verify KMS-encrypted uploads are denied
        with pytest.raises(botocore.exceptions.ClientError) as exc_info:
            s3_source.put_object(
                Bucket=source_bucket,
                Key="test-kms-denied.txt",
                Body=b"should be denied",
                ServerSideEncryption="aws:kms",
            )
        assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
        LOG.info("KMS upload correctly denied")


def _purge_object_lock_bucket(s3_client, bucket):
    """
    Delete every object version and delete marker in a bucket, bypassing
    GOVERNANCE retention, so a force_destroy bucket can be torn down even when
    locked objects remain.

    :param s3_client: boto3 S3 client in the bucket's region.
    :param bucket: Bucket name to purge.
    """
    paginator = s3_client.get_paginator("list_object_versions")
    for page in paginator.paginate(Bucket=bucket):
        for marker in page.get("Versions", []) + page.get("DeleteMarkers", []):
            s3_client.delete_object(
                Bucket=bucket,
                Key=marker["Key"],
                VersionId=marker["VersionId"],
                BypassGovernanceRetention=True,
            )


def _wait_for_replication(s3_replica, replica_bucket, test_key):
    """Poll the replica bucket until ``test_key`` appears (or time out)."""
    with timeout(300):
        while True:
            time.sleep(10)
            try:
                s3_replica.get_object(Bucket=replica_bucket, Key=test_key)
                LOG.info("Object %s replicated to %s", test_key, replica_bucket)
                return
            except s3_replica.exceptions.NoSuchKey:
                LOG.info("Object not yet replicated, retrying...")


@pytest.mark.parametrize("aws_provider_version", ["~> 6.0"], ids=["aws-6"])
@pytest.mark.parametrize(
    "retention",
    [
        None,
        {"mode": "GOVERNANCE", "days": 1},
    ],
    ids=["capability-only", "full-worm"],
)
def test_object_lock(
    boto3_session,
    test_role_arn,
    keep_after,
    aws_region,
    aws_provider_version,
    retention,
):
    # An HCL object literal accepts JSON syntax (colon-separated keys), so a
    # plain json.dumps of the dict is a valid tfvars value.
    enforced = retention is not None
    terraform_dir = osp.join(TERRAFORM_ROOT_DIR, "test_object_lock")
    state_files = [
        osp.join(terraform_dir, ".terraform"),
        osp.join(terraform_dir, ".terraform.lock.hcl"),
    ]

    for state_file in state_files:
        try:
            if osp.isdir(state_file):
                rmtree(state_file)
            elif osp.isfile(state_file):
                remove(state_file)
        except FileNotFoundError:
            pass

    with open(osp.join(terraform_dir, "terraform.tf"), "w") as fp:
        fp.write(dedent(f"""
                terraform {{
                  required_providers {{
                    aws = {{
                      source  = "hashicorp/aws"
                      version = "{aws_provider_version}"
                    }}
                  }}
                }}
                """))

    # Cross-region replication requires a destination region different from the
    # source, so derive it from aws_region instead of hardcoding.
    replica_region = "us-east-1" if aws_region == "us-west-1" else "us-west-1"

    with open(osp.join(terraform_dir, "terraform.tfvars"), "w") as fp:
        fp.write(dedent(f"""
                region             = "{aws_region}"
                replication_region = "{replica_region}"
                """))
        if test_role_arn:
            fp.write(dedent(f"""
                    role_arn      = "{test_role_arn}"
                    """))
        if retention is not None:
            fp.write(f"object_lock_default_retention = {json.dumps(retention)}\n")

    with terraform_apply(
        terraform_dir,
        destroy_after=not keep_after,
        json_output=True,
    ) as tf_output:
        LOG.info(json.dumps(tf_output, indent=4))

        source_bucket = tf_output["bucket_name"]["value"]
        replica_bucket = tf_output["replica_bucket_name"]["value"]

        assert replica_bucket is not None
        assert "-replica" in replica_bucket

        s3_source = boto3_session.client("s3", region_name=aws_region)
        s3_replica = boto3_session.client("s3", region_name=replica_region)

        # Both source and replica must have the Object Lock capability enabled.
        for client, bucket in (
            (s3_source, source_bucket),
            (s3_replica, replica_bucket),
        ):
            config = client.get_object_lock_configuration(Bucket=bucket)
            assert config["ObjectLockConfiguration"]["ObjectLockEnabled"] == "Enabled"
            rule = config["ObjectLockConfiguration"].get("Rule")
            if enforced:
                retention = rule["DefaultRetention"]
                assert retention["Mode"] == "GOVERNANCE"
                assert retention["Days"] == 1
            else:
                # Capability-only: no default retention rule is configured.
                assert rule is None

        # Replication still works with Object Lock enabled.
        test_key = "test-object-lock-replication.txt"
        s3_source.put_object(Bucket=source_bucket, Key=test_key, Body=b"locked content")
        _wait_for_replication(s3_replica, replica_bucket, test_key)

        if enforced:
            # A version under GOVERNANCE retention cannot be deleted without bypass.
            version_id = s3_source.head_object(Bucket=source_bucket, Key=test_key)[
                "VersionId"
            ]
            with pytest.raises(botocore.exceptions.ClientError) as exc_info:
                s3_source.delete_object(
                    Bucket=source_bucket,
                    Key=test_key,
                    VersionId=version_id,
                )
            assert exc_info.value.response["Error"]["Code"] == "AccessDenied"
            LOG.info("Locked version delete correctly denied without bypass")

            # With BypassGovernanceRetention the same delete succeeds.
            s3_source.delete_object(
                Bucket=source_bucket,
                Key=test_key,
                VersionId=version_id,
                BypassGovernanceRetention=True,
            )
            LOG.info("Locked version deleted with governance bypass")

        if not keep_after:
            # Locked object versions block force_destroy; purge them first.
            _purge_object_lock_bucket(s3_source, source_bucket)
            _purge_object_lock_bucket(s3_replica, replica_bucket)
