# Configuration

## Variables Reference

### Bucket Identity

#### `bucket_name`

- **Type:** `string`
- **Default:** `null`

Exact name for the S3 bucket. Mutually exclusive with `bucket_prefix` -
provide one or the other.

#### `bucket_prefix`

- **Type:** `string`
- **Default:** `null`

Prefix for the bucket name. AWS appends a unique suffix. Useful when you
don't need a predictable name.

### Security

#### `bucket_policy`

- **Type:** `string`
- **Default:** `""`

Additional JSON policy document to merge with the SSL-only enforcement
policy. Use `aws_iam_policy_document` data source to generate this.

#### `enable_acl`

- **Type:** `bool`
- **Default:** `false`

Enable ACL support. Required for CloudFront logging and S3 access logging
buckets. When enabled, also set `object_ownership` appropriately.

#### `acl`

- **Type:** `string`
- **Default:** `"private"`

Canned ACL to apply. Only used when `enable_acl = true`.

Allowed values: `private`, `log-delivery-write`, `aws-exec-read`,
`authenticated-read`.

Blocked values: `public-read`, `public-read-write` (conflict with public
access block).

#### `object_ownership`

- **Type:** `string`
- **Default:** `"BucketOwnerPreferred"`

Object ownership setting. Options:

- `BucketOwnerEnforced` - ACLs fully disabled (AWS best practice)
- `BucketOwnerPreferred` - Bucket owner gets ownership of ACL-uploaded objects
- `ObjectWriter` - Uploader retains ownership

#### `kms_key_arn`

- **Type:** `string`
- **Default:** `null`

ARN of a customer-managed KMS key (CMK) for SSE-KMS encryption at rest.

When `null` (the default), the bucket uses SSE-S3 (AES256) and KMS-encrypted
uploads are denied, which keeps cross-region replication working without any
replica-region KMS configuration.

When set:

- default bucket encryption becomes `aws:kms` with this key, and S3 Bucket
  Keys are enabled to cut KMS request cost;
- the deny-KMS-uploads guard is lifted and replaced with an enforcement policy
  that denies any explicit upload naming a different algorithm (e.g. `AES256`)
  or a different KMS key. Header-less uploads still fall through to the bucket
  default (this CMK), so callers do not have to set encryption headers.

Use SSE-KMS for **secret-grade** buckets that need an independent `kms:Decrypt`
gate and a per-decrypt CloudTrail trail on top of `s3:GetObject`, rather than
relying on IAM alone (as SSE-S3 does).

**Not compatible with `replication_region`.** KMS objects fail this module's
cross-region replication silently because the replica-region key and
replication-role grants are not managed here. A precondition enforces this: set
`kms_key_arn` only with `replication_region = null` and add a Vanta exemption
for `aws-s3-cross-region-replication-enabled`. Provision the CMK with
`registry.infrahouse.com/infrahouse/key/aws`.

### Data Protection

#### `enable_versioning`

- **Type:** `bool`
- **Default:** `false`

Enable object versioning. Automatically forced on when using
`replication_region` or `object_lock_enabled` (both require versioning).

#### `replication_region`

- **Type:** `string`
- **Default:** `null`

AWS region for the cross-region replica bucket. When set, creates a full
replica with identical security settings. Versioning is automatically
enabled on the source bucket (required by S3 for replication).

**Required unless exempted:** Either `replication_region` must be set or
a Vanta exemption for `aws-s3-cross-region-replication-enabled` must be
provided via `vanta_exemptions`. This is enforced at plan time.

Constraints:

- If using `bucket_name`: must be <= 55 characters (63 max minus 8 for
  `-replica` suffix)
- If using `bucket_prefix`: must be <= 29 characters (63 max minus 26-char
  AWS suffix minus 8 for `-replica`)

#### `replication_role_arn`

- **Type:** `string`
- **Default:** `null`

ARN of an existing IAM role for S3 to replicate with. Requires
`replication_region`; setting it without one fails at plan time.

When `null`, the module creates the replication role and its policy. When
set, the replication configuration uses your role, and the module creates
none of these:

- `aws_iam_role.replication`
- `aws_iam_role_policy.replication`
- `data.aws_iam_policy_document.replication_assume_role`
- `data.aws_iam_policy_document.replication_policy`

The role, its trust policy and its permissions are then yours to manage.
Use this to keep the role of a replication setup you move into the module
(see [Moving an existing replication setup into the module](#moving-an-existing-replication-setup-into-the-module)).

**The ARN must be known at plan time**, because it decides whether the module
creates its own role. The ARN of a role that already exists is. For a role you
create in the same apply, `aws_iam_role.example.arn` is not, and the plan fails
with `Invalid count argument`. Build the ARN as a string instead: Terraform
then knows it isn't null, and the replication configuration still waits for
the role.

```hcl
data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

module "bucket" {
  source = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  # ...

  bucket_name        = "my-critical-data"
  replication_region = "us-east-1"
  # A string template, not aws_iam_role.replication.arn: the role is
  # created in the same apply.
  replication_role_arn = "arn:aws:iam::${local.account_id}:role/${aws_iam_role.replication.name}"
}
```

##### What the role needs

A trust policy that lets S3 assume it:

```hcl
data "aws_iam_policy_document" "replication_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "replication" {
  name_prefix        = "my-replication-"
  assume_role_policy = data.aws_iam_policy_document.replication_assume_role.json
}
```

And the permissions the module grants its own role: read the source bucket's
replication configuration and object versions, and replicate into the
replica. `s3:GetObjectRetention` and `s3:GetObjectLegalHold` replicate Object
Lock metadata; S3 needs them when `object_lock_enabled = true`, and they are
harmless otherwise.

```hcl
data "aws_iam_policy_document" "replication" {
  statement {
    actions = [
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
    ]
    resources = [module.bucket.bucket_arn]
  }

  statement {
    actions = [
      "s3:GetObjectVersionForReplication",
      "s3:GetObjectVersionAcl",
      "s3:GetObjectVersionTagging",
      "s3:GetObjectRetention",
      "s3:GetObjectLegalHold",
    ]
    resources = ["${module.bucket.bucket_arn}/*"]
  }

  statement {
    actions = [
      "s3:ReplicateObject",
      "s3:ReplicateDelete",
      "s3:ReplicateTags",
    ]
    resources = ["${module.bucket.replica_bucket_arn}/*"]
  }
}

resource "aws_iam_role_policy" "replication" {
  name   = "s3-replication"
  role   = aws_iam_role.replication.id
  policy = data.aws_iam_policy_document.replication.json
}
```

The module waits for its own role's policy before it configures replication,
but it can't wait for yours. When you create the role and the module's
buckets in the same apply, replication can be configured a few seconds
before your policy is attached. The new buckets are empty at that point.

##### Moving an existing replication setup into the module

You may already manage a source bucket, a replica, their settings, a
replication role and a replication configuration yourself. To move them
into the module without touching the role:

1. Keep your `aws_iam_role` and `aws_iam_role_policy` as they are. Check that
   the policy grants at least the statements above.
2. Call the module with your bucket names, `replication_region`, and
   `replication_role_arn = aws_iam_role.replication.arn`. The role is in the
   state already, so its ARN is known at plan time.
3. Add a `moved` block for each bucket and setting the module now manages,
   for example:

    ```hcl
    moved {
      from = aws_s3_bucket.replica
      to   = module.bucket.aws_s3_bucket.replica[0]
    }

    moved {
      from = aws_s3_bucket_versioning.replica
      to   = module.bucket.aws_s3_bucket_versioning.replica[0]
    }

    moved {
      from = aws_s3_bucket_replication_configuration.this
      to   = module.bucket.aws_s3_bucket_replication_configuration.this[0]
    }
    ```

4. Plan. Nothing may be destroyed. The replication configuration is moved,
   and keeps your role; it may be updated in place where your rule differs
   from the module's (`replicate-all`, all objects, delete markers,
   `STANDARD_IA`).

Without `replication_role_arn`, the module creates its own role and
Terraform destroys yours. It destroys it before the replication
configuration moves to the new role, so replication points at a deleted role
until the update finishes, and objects written in that window fail to
replicate ([#34](https://github.com/infrahouse/terraform-aws-s3-bucket/issues/34)).

##### Switching from the module's role to your own

A deployment applied without `replication_role_arn` replicates with the
module's role. To move it to a role you manage, use two applies:

1. Upgrade the module to a version that has `replication_role_arn`, change
   nothing else, and apply. The plan shows no changes, but the apply records
   `create_before_destroy` for the module's role and policy in the state.
2. Set `replication_role_arn` and apply. Terraform updates the replication
   configuration to your role first, and only then deletes the module's
   policy and role.

**Don't combine the two steps when you upgrade from 0.9.0 or earlier.** For an
object it deletes, Terraform reads `create_before_destroy` from the state, and
the state has it only after step 1. In one apply, Terraform deletes the
module's role before it updates the replication configuration: replication
points at a deleted role until the update finishes, and objects written in
that window fail to replicate. A module that wraps this one needs a release
that only upgrades it before a release that sets `replication_role_arn`.

#### `object_lock_enabled`

- **Type:** `bool`
- **Default:** `false`

Enable S3 Object Lock (WORM) on the bucket. This is a **create-time only**
capability and **cannot be disabled** later; it also forces versioning on.
When replication is configured, the replica bucket gets Object Lock enabled
too, which is what allows a locked source bucket to replicate at all (AWS
rejects replication when the source is locked but the destination is not).

Enabling the capability alone does **not** make objects immutable - it only
permits retention. Set `object_lock_default_retention` to actually enforce
WORM. A `check` block warns when the capability is on without retention.

#### `object_lock_default_retention`

- **Type:** `object({ mode = string, days = optional(number), years = optional(number) })`
- **Default:** `null`

Default retention applied to every new object version on both the source and
the replica. Requires `object_lock_enabled = true`.

- `mode` - `GOVERNANCE` (privileged users can bypass with
  `s3:BypassGovernanceRetention`) or `COMPLIANCE` (no one can delete or
  shorten until retention expires, not even the root account).
- Specify **exactly one** of `days` or `years`.

```hcl
object_lock_enabled = true
object_lock_default_retention = {
  mode = "GOVERNANCE"
  days = 30
}
```

When `null`, the bucket is capability-only: Object Lock is enabled but no
retention is enforced.

### Lifecycle

#### `force_destroy`

- **Type:** `bool`
- **Default:** `false`

Allow the bucket to be destroyed even if it contains objects. Applies to
both source and replica buckets.

### Compliance

#### `vanta_exemptions`

- **Type:** `map(string)`
- **Default:** `{}`

Map of Vanta test slugs to exemption reasons. Each entry adds a tag
`vanta-exempt:<slug> = <reason>` to the bucket. A reconciler Lambda in
`terraform-aws-org-governance` reads these tags and calls the Vanta
per-test deactivation API.

Known test slugs:

- `aws-s3-cross-region-replication-enabled`

Reasons must be 1-256 characters, using only letters, digits, spaces,
and `+ - = . _ : / @`.

```hcl
module "lambda_artifacts" {
  source  = "registry.infrahouse.com/infrahouse/s3-bucket/aws"
  version = "0.5.0"

  bucket_prefix = "my-lambda-artifacts"

  vanta_exemptions = {
    "aws-s3-cross-region-replication-enabled" = "Lambda artifact bucket - ephemeral build output. No DR value"
  }
}
```

Note: replica buckets are automatically exempt from the CRR test — the
module hardcodes the exemption tag since testing a replica for replication
is nonsensical.

### Metadata

#### `tags`

- **Type:** `map(string)`
- **Default:** `{}`

Tags to apply to the S3 bucket. When `replication_region` is set, they also
go on the replica bucket and the replication IAM role. The module merges its
defaults first, then your `tags`, then the values it always sets:

| Tag | Source bucket | Replica bucket | Replication IAM role |
|-----|---------------|----------------|----------------------|
| `created_by_module` | `infrahouse/s3-bucket/aws` (default) | same (default) | same (default) |
| `module_version` | this module's version | this module's version | this module's version |
| `Name` | your `Name` | `<your Name>-replica` | your `Name` |
| `vanta-exempt:<slug>` | from `vanta_exemptions` | from `vanta_exemptions`, plus the CRR exemption | not set |

- `module_version` is always this module's version. It records which
  version of this module manages the resource, so a `module_version` you
  pass in `tags` is overridden on all three resources. It is the only one of
  the module's default tags that overrides yours.
- `created_by_module` is a default: a `created_by_module` in your `tags`
  replaces it on all three resources.
- `Name` comes from your `tags`. The replica gets its own,
  `<your Name>-replica`, so the console, Vanta and cost reports don't show
  two buckets with the same `Name`. The role keeps your `Name` as-is, which
  links the generic `s3-replication-*` role back to its bucket. If you set no
  `Name` in `tags`, the module sets none.
- All your other tags go on all three resources unchanged.
- The provider's `default_tags` apply too, but resource tags win over them,
  so `module_version` and the replica's `Name` still hold when `default_tags`
  are set. The module doesn't read `default_tags`: a `Name` set only there is
  copied unchanged onto all three resources and gets no `-replica` suffix.
  Set `Name` in `tags` to get the suffix.

```hcl
module "backups" {
  # source and version as in the examples above

  bucket_name        = "my-backups"
  replication_region = "us-east-1"

  tags = {
    Name    = "my-backups"
    service = "backup"
  }
}
# Source bucket:  Name = "my-backups"
# Replica bucket: Name = "my-backups-replica"
# IAM role:       Name = "my-backups"
```

**Upgrading from 0.9.0 or earlier:** the first plan updates tags in place.
The replica bucket gets the new `Name` and `module_version` (if you set them
in `tags`). The replication IAM role, which had only the provider's default
tags, gets the module's and your tags. Nothing is replaced.
