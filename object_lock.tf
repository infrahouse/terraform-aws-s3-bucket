resource "aws_s3_bucket_object_lock_configuration" "this" {
  count  = var.object_lock_enabled && var.object_lock_default_retention != null ? 1 : 0
  bucket = aws_s3_bucket.this.id

  rule {
    default_retention {
      mode  = var.object_lock_default_retention.mode
      days  = var.object_lock_default_retention.days
      years = var.object_lock_default_retention.years
    }
  }
}

# Soft nudge: Object Lock capability without default retention is non-enforcing
# (WORM is not actually applied). Warn rather than fail - capability-only is a
# legitimate state (e.g. retention driven solely by per-object settings).
check "object_lock_non_enforcing" {
  assert {
    condition     = !var.object_lock_enabled || var.object_lock_default_retention != null
    error_message = <<-EOT
      object_lock_enabled is true but object_lock_default_retention is null:
      the Object Lock capability is on but no retention is enforced, so objects
      are NOT immutable. Set object_lock_default_retention to enforce WORM.
    EOT
  }
}
