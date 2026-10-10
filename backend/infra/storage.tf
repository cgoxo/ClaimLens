resource "google_storage_bucket" "claims" {
  name                        = "${var.project}-claimlens"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true

  # claim documents are sensitive: keep them 30 days only
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
  depends_on = [google_project_service.apis]
}
