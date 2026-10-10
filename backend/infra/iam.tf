resource "google_service_account" "api" {
  account_id   = "claimlens-api"
  display_name = "ClaimLens API (Cloud Run)"
}

resource "google_project_iam_member" "api" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/datastore.user",
    "roles/documentai.apiUser",
    "roles/firebaseauth.viewer",
  ])
  project = var.project
  role    = each.value
  member  = "serviceAccount:${google_service_account.api.email}"
}

# only its own bucket
resource "google_storage_bucket_iam_member" "api" {
  bucket = google_storage_bucket.claims.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.api.email}"
}
