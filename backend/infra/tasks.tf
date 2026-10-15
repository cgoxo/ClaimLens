# Job queue: the API enqueues HTTP tasks; Cloud Tasks calls back POST /internal/jobs/{kind} on the
# service with an OIDC token for claimlens-tasks, which the endpoint verifies.

resource "google_cloud_tasks_queue" "jobs" {
  name     = "claimlens-jobs"
  location = var.region

  rate_limits {
    max_concurrent_dispatches = 10
  }

  retry_config {
    max_attempts = 3
    min_backoff  = "10s"
  }

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "tasks" {
  account_id   = "claimlens-tasks"
  display_name = "ClaimLens job queue (Cloud Tasks caller)"
}

# the API may add tasks to this queue only
resource "google_cloud_tasks_queue_iam_member" "api_enqueue" {
  name     = google_cloud_tasks_queue.jobs.name
  location = google_cloud_tasks_queue.jobs.location
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${google_service_account.api.email}"
}

# the API may mint OIDC tokens as the tasks account (put on each task it creates)
resource "google_service_account_iam_member" "api_acts_as_tasks" {
  service_account_id = google_service_account.tasks.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.api.email}"
}

# the tasks account may call the service
resource "google_cloud_run_service_iam_member" "tasks_invoke" {
  service  = "claimlens-api"
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.tasks.email}"
}
