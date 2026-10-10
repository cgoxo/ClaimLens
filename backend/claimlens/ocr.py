from typing import Protocol

from claimlens.models import Span


class Ocr(Protocol):
    def read_page(self, png: bytes, doc: str, page: int, width: float, height: float) -> list[Span]: ...


class NoOcr:
    """OCR switched off: scanned and photo pages stay unreadable."""

    def read_page(self, png: bytes, doc: str, page: int, width: float, height: float) -> list[Span]:
        return []


class DocAiOcr:
    """Document AI Enterprise OCR: words with boxes and confidence, including handwriting."""

    def __init__(self, project: str, location: str, processor: str):
        from google.cloud import documentai

        self.client = documentai.DocumentProcessorServiceClient(
            client_options={"api_endpoint": f"{location}-documentai.googleapis.com"})
        self.name = processor if processor.startswith("projects/") else \
            self.client.processor_path(project, location, processor)

    def read_page(self, png: bytes, doc: str, page: int, width: float, height: float) -> list[Span]:
        result = self.client.process_document(request={
            "name": self.name, "raw_document": {"content": png, "mime_type": "image/png"}})
        document = result.document
        spans = []
        for n, token in enumerate(document.pages[0].tokens if document.pages else []):
            layout = token.layout
            text = "".join(document.text[int(s.start_index):int(s.end_index)]
                           for s in layout.text_anchor.text_segments).strip()
            xs = [v.x * width for v in layout.bounding_poly.normalized_vertices]
            ys = [v.y * height for v in layout.bounding_poly.normalized_vertices]
            if text and xs:
                spans.append(Span(doc=doc, page=page, text=text, font="ocr", size=0,
                                  bbox=(min(xs), min(ys), max(xs), max(ys)), seqno=n,
                                  confidence=layout.confidence or 0.0))
        return spans
