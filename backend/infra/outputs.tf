output "bucket" {
  value = google_storage_bucket.claims.name
}

output "docai_processor_id" {
  value = google_document_ai_processor.ocr.id
}

output "service_account_email" {
  value = google_service_account.api.email
}

output "registry" {
  value = "${var.region}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.claimlens.repository_id}"
}

output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "deployer_email" {
  value = google_service_account.deployer.email
}

output "tasks_queue" {
  value = google_cloud_tasks_queue.jobs.name
}

output "tasks_sa_email" {
  value = google_service_account.tasks.email
}
