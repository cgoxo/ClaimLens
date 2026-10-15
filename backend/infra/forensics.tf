# CAT-Net pixel forensics: a GPU Cloud Run Job, run per batch (measurement now, per case in Phase 2).
# Singapore: L4 GPUs are open there; Mumbai is invitation-only. Billing only while an execution runs.

variable "forensics_image" {
  description = "CAT-Net image in Artifact Registry (built by forensics/catnet/cloudbuild.yaml)"
  type        = string
  default     = "asia-south1-docker.pkg.dev/social-pulse-510513/claimlens/claimlens-forensics:1be417a"
}

resource "google_service_account" "forensics" {
  account_id   = "claimlens-forensics"
  display_name = "ClaimLens pixel forensics job (CAT-Net)"
}

# reads images and writes heatmaps in the claims bucket
resource "google_storage_bucket_iam_member" "forensics" {
  bucket = google_storage_bucket.claims.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.forensics.email}"
}

# pulls its image
resource "google_artifact_registry_repository_iam_member" "forensics_pull" {
  location   = google_artifact_registry_repository.claimlens.location
  repository = google_artifact_registry_repository.claimlens.repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.forensics.email}"
}

resource "google_cloud_run_v2_job" "forensics" {
  count               = var.forensics_image == "" ? 0 : 1
  name                = "claimlens-forensics"
  location            = "asia-southeast1"
  deletion_protection = false

  template {
    task_count = 1
    template {
      service_account = google_service_account.forensics.email
      max_retries     = 0
      timeout         = "3600s"
      containers {
        image = var.forensics_image
        resources {
          limits = {
            cpu              = "4"
            memory           = "16Gi"
            "nvidia.com/gpu" = "1"
          }
        }
      }
      node_selector {
        accelerator = "nvidia-l4"
      }
      gpu_zonal_redundancy_disabled = true
    }
  }
  depends_on = [google_project_service.apis]
}

# the API (Phase 2) may start this job, and only this job
resource "google_cloud_run_v2_job_iam_member" "api_runs_forensics" {
  count    = var.forensics_image == "" ? 0 : 1
  name     = google_cloud_run_v2_job.forensics[0].name
  location = google_cloud_run_v2_job.forensics[0].location
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.api.email}"
}
