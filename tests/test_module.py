import json
from os import path as osp, remove
from shutil import rmtree
from textwrap import dedent

import boto3
import pytest
from pytest_infrahouse import terraform_apply

from tests.conftest import (
    LOG,
    TERRAFORM_ROOT_DIR,
)


@pytest.mark.parametrize(
    "aws_provider_version", ["~> 5.31", "~> 6.0"], ids=["aws-5", "aws-6"]
)
def test_module(
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
            # File was already removed by another process
            pass

    # Write terraform.tfvars
    with open(osp.join(terraform_dir, "terraform.tfvars"), "w") as fp:
        fp.write(
            dedent(
                f"""
                region          = "{aws_region}"
                """
            )
        )
        if test_role_arn:
            fp.write(
                dedent(
                    f"""
                    role_arn      = "{test_role_arn}"
                    """
                )
            )

    # Update terraform.tf with the specific AWS provider version
    with open(osp.join(terraform_dir, "terraform.tf"), "w") as fp:
        fp.write(
            dedent(
                f"""
                terraform {{
                  required_providers {{
                    aws = {{
                      source  = "hashicorp/aws"
                      version = "{aws_provider_version}"
                    }}
                  }}
                }}
                """
            )
        )
    with terraform_apply(
        terraform_dir,
        destroy_after=not keep_after,
        json_output=True,
    ) as tf_output:
        LOG.info(json.dumps(tf_output, indent=4))


def _build_s3_client(test_role_arn: str, aws_region: str) -> boto3.client:
    """
    Build an S3 client, assuming the test role if provided.

    :param test_role_arn: ARN of the IAM role to assume, or None for default credentials
    :param aws_region: AWS region for the client
    :return: boto3 S3 client
    """
    if test_role_arn:
        sts = boto3.client("sts", region_name=aws_region)
        creds = sts.assume_role(
            RoleArn=test_role_arn,
            RoleSessionName="test-s3-bucket",
        )["Credentials"]
        return boto3.client(
            "s3",
            region_name=aws_region,
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
        )
    return boto3.client("s3", region_name=aws_region)


@pytest.mark.parametrize(
    "aws_provider_version", ["~> 5.31", "~> 6.0"], ids=["aws-5", "aws-6"]
)
def test_kms_encryption(
    test_role_arn,
    keep_after,
    aws_region,
    aws_provider_version,
):
    """Test that KMS encryption is correctly configured when kms_key_arn is provided."""
    terraform_dir = osp.join(TERRAFORM_ROOT_DIR, "test_kms")
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

    with open(osp.join(terraform_dir, "terraform.tfvars"), "w") as fp:
        fp.write(
            dedent(
                f"""
                region          = "{aws_region}"
                """
            )
        )
        if test_role_arn:
            fp.write(
                dedent(
                    f"""
                    role_arn      = "{test_role_arn}"
                    """
                )
            )

    with open(osp.join(terraform_dir, "terraform.tf"), "w") as fp:
        fp.write(
            dedent(
                f"""
                terraform {{
                  required_providers {{
                    aws = {{
                      source  = "hashicorp/aws"
                      version = "{aws_provider_version}"
                    }}
                  }}
                }}
                """
            )
        )
    with terraform_apply(
        terraform_dir,
        destroy_after=not keep_after,
        json_output=True,
    ) as tf_output:
        LOG.info(json.dumps(tf_output, indent=4))
        s3_client = _build_s3_client(test_role_arn, aws_region)

        # Verify KMS-encrypted bucket uses SSE-KMS with bucket key
        kms_bucket = tf_output["kms_bucket_name"]["value"]
        kms_enc = s3_client.get_bucket_encryption(Bucket=kms_bucket)
        kms_rules = kms_enc["ServerSideEncryptionConfiguration"]["Rules"]
        assert len(kms_rules) == 1
        kms_default = kms_rules[0]["ApplyServerSideEncryptionByDefault"]
        assert kms_default["SSEAlgorithm"] == "aws:kms", (
            f"Expected aws:kms, got {kms_default['SSEAlgorithm']}"
        )
        assert kms_default["KMSMasterKeyID"] == tf_output["kms_key_arn"]["value"], (
            "KMS key ARN mismatch"
        )
        assert kms_rules[0]["BucketKeyEnabled"] is True, (
            "Bucket key should be enabled for SSE-KMS"
        )

        # Verify default bucket still uses AES256
        default_bucket = tf_output["default_bucket_name"]["value"]
        default_enc = s3_client.get_bucket_encryption(Bucket=default_bucket)
        default_rules = default_enc["ServerSideEncryptionConfiguration"]["Rules"]
        assert len(default_rules) == 1
        default_algo = default_rules[0]["ApplyServerSideEncryptionByDefault"]
        assert default_algo["SSEAlgorithm"] == "AES256", (
            f"Expected AES256, got {default_algo['SSEAlgorithm']}"
        )
