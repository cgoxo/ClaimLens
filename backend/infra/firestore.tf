resource "google_firestore_database" "claimlens" {
  name                    = "claimlens"
  location_id             = var.region
  type                    = "FIRESTORE_NATIVE"
  delete_protection_state = "DELETE_PROTECTION_DISABLED"
  deletion_policy         = "DELETE"
  depends_on              = [google_project_service.apis]
}

# Daily chat limit: count_messages_since queries every case's messages by owner, role and time.
resource "google_firestore_index" "chat_messages_by_owner" {
  project     = google_firestore_database.claimlens.project
  database    = google_firestore_database.claimlens.name
  collection  = "messages"
  query_scope = "COLLECTION_GROUP"

  fields {
    field_path = "by"
    order      = "ASCENDING"
  }
  fields {
    field_path = "role"
    order      = "ASCENDING"
  }
  fields {
    field_path = "created_at"
    order      = "ASCENDING"
  }
}
