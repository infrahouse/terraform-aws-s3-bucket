import json
import time
from os import path as osp, remove
from shutil import rmtree
from textwrap import dedent

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
