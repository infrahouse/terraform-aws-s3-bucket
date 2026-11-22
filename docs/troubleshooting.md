# Troubleshooting

## Common Issues

### "bucket_name must be <= 55 characters when replication is enabled"

**Problem:** Your bucket name is too long to append `-replica` and stay
within S3's 63-character limit.

**Solution:** Shorten the bucket name to 55 characters or fewer.

### "bucket_prefix must be <= 29 characters when replication is enabled"

**Problem:** Your bucket prefix is too long. With replication enabled,
the replica gets `-replica` appended to the prefix, plus AWS adds a
26-character unique suffix.

**Solution:** Shorten the prefix to 29 characters or fewer.

### "S3 cross-region replication is required"

**Problem:** Neither `replication_region` nor a Vanta exemption for
`aws-s3-cross-region-replication-enabled` was provided.

**Solution:** Either enable replication or declare an exemption:

```hcl
# Option 1: enable replication
module "bucket" {
  # ...
  replication_region = "us-east-1"
}

# Option 2: exempt from the Vanta test
module "bucket" {
  # ...
  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "Reason replication is unnecessary"
  }
}
```

### "Invalid count argument" with `replication_role_arn`

**Problem:** You pass the ARN of a role created in the same apply, e.g.
`replication_role_arn = aws_iam_role.replication.arn`. Whether the module
creates its own role depends on that value, and Terraform doesn't know it
until the role exists.

**Solution:** Build the ARN as a string. Terraform then knows at plan time that
it isn't null:

```hcl
locals {
  account_id = data.aws_caller_identity.current.account_id
}

module "bucket" {
  # ...
  replication_role_arn = "arn:aws:iam::${local.account_id}:role/${aws_iam_role.replication.name}"
}
```

### "replication_role_arn must be an IAM role ARN"

**Problem:** `replication_role_arn` is not a role ARN, for example a role name.

**Solution:** Pass the full ARN, `arn:aws:iam::<account-id>:role/<role-name>`.

### "replication_role_arn is set, but replication_region is null"

**Problem:** You passed a replication role, but replication is off.

**Solution:** Set `replication_region`, or remove `replication_role_arn`.

### "ACLs cannot be enabled when object_ownership is BucketOwnerEnforced"

**Problem:** You set `enable_acl = true` with the default or explicit
`object_ownership = "BucketOwnerEnforced"`.

**Solution:** Use `BucketOwnerPreferred` or `ObjectWriter`:

```hcl
module "logs" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.10.0"

  bucket_name      = "my-logs"
  enable_acl       = true
  object_ownership = "BucketOwnerPreferred"

  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "Log bucket - replicated via log aggregation pipeline"
  }
}
```

### PermanentRedirect errors on replica resources

**Problem:** You're using AWS provider < 6.0. The module uses the v6
per-resource `region` argument for replica resources.

**Solution:** Upgrade to AWS provider >= 6.0:

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
```

### Bucket not empty on destroy

**Problem:** `terraform destroy` fails because the bucket contains objects.

**Solution:** Set `force_destroy = true` if you want Terraform to empty
and delete the bucket. Note: this deletes all objects permanently.

### Replication lag

**Problem:** Objects don't appear in the replica immediately.

**Explanation:** S3 cross-region replication is asynchronous. Most objects
replicate within 15 minutes, but large objects or high-throughput workloads
may take longer. This is normal AWS behavior, not a module issue.
