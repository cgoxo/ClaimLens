# Firebase web API key: public by nature (it ships in the site's JavaScript) but kept out of git.
# The value is added with gcloud (never stored in Terraform state); builds read it at build time.

resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_secret_manager_secret" "firebase_web_api_key" {
  secret_id = "claimlens-firebase-web-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.secretmanager]
}

locals {
  firebase_key_readers = {
    deployer    = "serviceAccount:${google_service_account.deployer.email}"           # GitHub Actions builds
    cloud_build = "serviceAccount:538594533263-compute@developer.gserviceaccount.com" # make deploy (Cloud Build)
  }
}

resource "google_secret_manager_secret_iam_member" "firebase_key_readers" {
  for_each  = local.firebase_key_readers
  secret_id = google_secret_manager_secret.firebase_web_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = each.value
}
