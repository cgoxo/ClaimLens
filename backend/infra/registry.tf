resource "google_artifact_registry_repository" "claimlens" {
  location      = var.region
  repository_id = "claimlens"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}
