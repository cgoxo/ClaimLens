# Shared project with SocialPulse: never turn APIs off when ClaimLens is destroyed.
locals {
  apis = [
    "firestore.googleapis.com",
    "aiplatform.googleapis.com",
    "documentai.googleapis.com",
    "storage.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "identitytoolkit.googleapis.com",
    "firebase.googleapis.com",
    "cloudtasks.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}
