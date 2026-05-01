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
def test_lifecycle(
    test_role_arn,
    keep_after,
    aws_region,
    aws_provider_version,
):
    """Test that lifecycle rules are correctly configured."""
    terraform_dir = osp.join(TERRAFORM_ROOT_DIR, "test_lifecycle")
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

        lifecycle_bucket = tf_output["lifecycle_bucket_name"]["value"]
        lifecycle_config = s3_client.get_bucket_lifecycle_configuration(
            Bucket=lifecycle_bucket
        )
        rules = lifecycle_config["Rules"]
        assert len(rules) == 2, f"Expected 2 lifecycle rules, got {len(rules)}"

        rule_ids = {r["ID"] for r in rules}
        assert "expire-old-versions" in rule_ids, (
            "Missing expire-old-versions rule"
        )
        assert "abort-incomplete-uploads" in rule_ids, (
            "Missing abort-incomplete-uploads rule"
        )

        for rule in rules:
            if rule["ID"] == "expire-old-versions":
                assert rule["Status"] == "Enabled"
                assert rule["NoncurrentVersionExpiration"]["NoncurrentDays"] == 30
            elif rule["ID"] == "abort-incomplete-uploads":
                assert rule["Status"] == "Enabled"
                assert (
                    rule["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"]
                    == 7
                )

        no_lifecycle_bucket = tf_output["no_lifecycle_bucket_name"]["value"]
        try:
            s3_client.get_bucket_lifecycle_configuration(
                Bucket=no_lifecycle_bucket
            )
            pytest.fail("Expected no lifecycle config on bucket without rules")
        except s3_client.exceptions.ClientError as exc:
            assert exc.response["Error"]["Code"] == "NoSuchLifecycleConfiguration"

        expiration_bucket = tf_output["expiration_bucket_name"]["value"]
        exp_config = s3_client.get_bucket_lifecycle_configuration(
            Bucket=expiration_bucket
        )
        exp_rules = exp_config["Rules"]
        assert len(exp_rules) == 1, f"Expected 1 rule, got {len(exp_rules)}"
        assert exp_rules[0]["ID"] == "expire-all"
        assert exp_rules[0]["Expiration"]["Days"] == 90
        assert exp_rules[0]["Filter"]["Prefix"] == "logs/"
