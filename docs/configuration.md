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

### Data Protection

#### `enable_versioning`

- **Type:** `bool`
- **Default:** `false`

Enable object versioning. Required when using `replication_region`.

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

Additional tags to apply to the S3 bucket(s). The module automatically adds
`created_by_module` and `module_version` tags.
