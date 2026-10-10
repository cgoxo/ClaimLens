resource "google_document_ai_processor" "ocr" {
  location     = var.docai_location
  display_name = "claimlens-ocr"
  type         = "OCR_PROCESSOR"
  depends_on   = [google_project_service.apis]
}
