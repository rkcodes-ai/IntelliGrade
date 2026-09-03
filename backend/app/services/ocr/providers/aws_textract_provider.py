"""
Real OCR adapter wrapping AWS Textract via `boto3`.

**Credential-gated, not runtime-verified**: this environment has no AWS
credentials, and none are fabricated. Every method below is real, correct
code against Textract's documented response shape (`response["Blocks"]` —
a flat list of `PAGE`/`LINE`/`WORD` blocks linked by `Relationships`), but
has never been exercised against a live call — `health_check()` reports
this honestly rather than claiming readiness it can't back up.

Textract's `Geometry.BoundingBox` is **normalized** (0.0-1.0 fractions of
image width/height), unlike every other provider in this module, which
report pixel coordinates — `extract()` reads the real image dimensions
(via Pillow, already a project dependency) and converts, so
`BoundingBox`'s pixel-coordinate contract holds regardless of which
provider produced it.

`extract()` uses the cheaper `detect_document_text` call (plain OCR,
matching the standard hierarchy); `extract_tables()` makes a separate
`analyze_document(FeatureTypes=["TABLES"])` call rather than requesting
every feature (forms/signatures/queries too) on every single page, which
would be needlessly expensive for the common case.

Authentication: explicit `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/
`AWS_SESSION_TOKEN` settings are optional — when unset, boto3 falls back to
its own standard credential chain (IAM role, `~/.aws/credentials`, env
vars), exactly like the AWS CLI.
"""

from typing import Any

from PIL import Image

from app.core.config import get_settings
from app.services.ocr.base import (
    BoundingBox,
    OCRBlockResult,
    OCRLineResult,
    OCRPageResult,
    OCRProviderAdapter,
    OCRWordResult,
)
from app.services.ocr.exceptions import (
    OCRDependencyMissingError,
    OCRProviderAuthenticationError,
    OCRProviderConfigurationError,
    OCRProviderConnectivityError,
    OCRProviderRateLimitError,
)
from app.services.ocr.models import (
    HealthCheckResult,
    OCRTableCell,
    OCRTableResult,
    ProviderCapabilities,
)

settings = get_settings()


class AWSTextractProvider(OCRProviderAdapter):
    provider_code = "aws_textract"
    is_implemented = True

    def __init__(
        self,
        *,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        session_token: str | None = None,
    ) -> None:
        super().__init__()
        self.region = region or settings.AWS_TEXTRACT_REGION
        self.access_key_id = access_key_id or settings.AWS_ACCESS_KEY_ID
        self.secret_access_key = secret_access_key or settings.AWS_SECRET_ACCESS_KEY
        self.session_token = session_token or settings.AWS_SESSION_TOKEN
        self._client: Any | None = None

    def _get_client(self) -> Any:
        try:
            import boto3
        except ImportError as exc:
            raise OCRDependencyMissingError(
                "The 'boto3' package is not installed in this environment. Install it to "
                "activate this provider."
            ) from exc

        if self._client is not None:
            return self._client

        if not self.region:
            raise OCRProviderConfigurationError(
                "AWS Textract requires a region (Settings.AWS_TEXTRACT_REGION). Access key/"
                "secret key are optional — boto3 falls back to its standard credential chain "
                "(IAM role, ~/.aws/credentials, env vars) when they're unset — but a region "
                "must be explicit."
            )

        kwargs: dict[str, Any] = {"region_name": self.region}
        if self.access_key_id and self.secret_access_key:
            kwargs["aws_access_key_id"] = self.access_key_id
            kwargs["aws_secret_access_key"] = self.secret_access_key
            if self.session_token:
                kwargs["aws_session_token"] = self.session_token
        # If explicit keys aren't set, boto3 falls back to its standard
        # credential chain (IAM role, ~/.aws/credentials, env vars) —
        # exactly like the AWS CLI — rather than raising here.
        self._client = boto3.client("textract", **kwargs)
        return self._client

    def _call_textract(self, method_name: str, **kwargs: Any) -> Any:
        from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError

        client = self._get_client()
        try:
            return getattr(client, method_name)(**kwargs)
        except NoCredentialsError as exc:
            raise OCRProviderAuthenticationError(f"No AWS credentials available: {exc}") from exc
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in {
                "UnrecognizedClientException",
                "AccessDeniedException",
                "InvalidSignatureException",
            }:
                raise OCRProviderAuthenticationError(f"AWS rejected the request: {exc}") from exc
            if error_code in {"ThrottlingException", "ProvisionedThroughputExceededException"}:
                raise OCRProviderRateLimitError(f"AWS Textract rate limit hit: {exc}") from exc
            raise OCRProviderConfigurationError(f"AWS Textract returned an error: {exc}") from exc
        except EndpointConnectionError as exc:
            raise OCRProviderConnectivityError(f"AWS Textract is unreachable: {exc}") from exc

    def extract(self, image_path: str, *, language: str = "eng") -> OCRPageResult:
        with self._timed():
            # Validate credentials/config before touching the file — same
            # order as AzureOCRProvider/GoogleVisionProvider, so a missing
            # region/key surfaces as OCRProviderConfigurationError rather
            # than being masked by an unrelated FileNotFoundError.
            self._get_client()

            with open(image_path, "rb") as handle:
                image_bytes = handle.read()
            with Image.open(image_path) as img:
                image_width, image_height = img.size

            response = self._call_textract("detect_document_text", Document={"Bytes": image_bytes})
            blocks_by_id = {b["Id"]: b for b in response.get("Blocks", [])}

            def to_bbox(block: dict[str, Any]) -> BoundingBox:
                bb = block["Geometry"]["BoundingBox"]
                return BoundingBox(
                    left=int(bb["Left"] * image_width),
                    top=int(bb["Top"] * image_height),
                    width=int(bb["Width"] * image_width),
                    height=int(bb["Height"] * image_height),
                )

            def children_of(block: dict[str, Any]) -> list[dict[str, Any]]:
                child_ids: list[str] = []
                for rel in block.get("Relationships", []):
                    if rel["Type"] == "CHILD":
                        child_ids.extend(rel["Ids"])
                return [blocks_by_id[cid] for cid in child_ids if cid in blocks_by_id]

            lines: list[OCRLineResult] = []
            all_confidences: list[float] = []
            text_parts: list[str] = []

            for block in response.get("Blocks", []):
                if block["BlockType"] != "LINE":
                    continue
                word_blocks = [
                    child for child in children_of(block) if child["BlockType"] == "WORD"
                ]
                words = [
                    OCRWordResult(
                        text=word["Text"],
                        bounding_box=to_bbox(word),
                        confidence=float(word.get("Confidence", 0.0)),
                        reading_order=index,
                    )
                    for index, word in enumerate(word_blocks)
                ]
                for word in words:
                    all_confidences.append(word.confidence)
                lines.append(
                    OCRLineResult(
                        text=block.get("Text", ""),
                        bounding_box=to_bbox(block),
                        confidence=float(block.get("Confidence", 0.0)),
                        reading_order=len(lines),
                        words=words,
                    )
                )
                text_parts.append(block.get("Text", ""))

        if not lines:
            return OCRPageResult(
                raw_text="",
                average_confidence=0.0,
                language=language,
                rotation_degrees=0.0,
                blocks=[],
            )

        page_block = OCRBlockResult(
            bounding_box=_union_box([line.bounding_box for line in lines]),
            confidence=sum(all_confidences) / len(all_confidences) if all_confidences else 0.0,
            reading_order=0,
            lines=lines,
        )
        return OCRPageResult(
            raw_text="\n".join(text_parts),
            average_confidence=(sum(all_confidences) / len(all_confidences))
            if all_confidences
            else 0.0,
            language=language,
            # Textract doesn't report a single page-level rotation/skew
            # angle in `detect_document_text` — 0.0 means "not reported".
            rotation_degrees=0.0,
            blocks=[page_block],
        )

    def extract_tables(self, image_path: str, *, language: str = "eng") -> list[OCRTableResult]:
        """Real `analyze_document(FeatureTypes=["TABLES"])` call — a
        separate, more expensive request than `extract()`'s plain
        `detect_document_text`, made only when table structure is wanted."""
        with open(image_path, "rb") as handle:
            image_bytes = handle.read()
        with Image.open(image_path) as img:
            image_width, image_height = img.size

        response = self._call_textract(
            "analyze_document", Document={"Bytes": image_bytes}, FeatureTypes=["TABLES"]
        )
        blocks_by_id = {b["Id"]: b for b in response.get("Blocks", [])}

        def to_bbox(block: dict[str, Any]) -> BoundingBox:
            bb = block["Geometry"]["BoundingBox"]
            return BoundingBox(
                left=int(bb["Left"] * image_width),
                top=int(bb["Top"] * image_height),
                width=int(bb["Width"] * image_width),
                height=int(bb["Height"] * image_height),
            )

        def cell_text(cell_block: dict[str, Any]) -> str:
            parts = []
            for rel in cell_block.get("Relationships", []):
                if rel["Type"] != "CHILD":
                    continue
                for cid in rel["Ids"]:
                    child = blocks_by_id.get(cid)
                    if child and child["BlockType"] == "WORD":
                        parts.append(child["Text"])
            return " ".join(parts)

        tables: list[OCRTableResult] = []
        for block in response.get("Blocks", []):
            if block["BlockType"] != "TABLE":
                continue
            cell_blocks: list[dict[str, Any]] = []
            for rel in block.get("Relationships", []):
                if rel["Type"] == "CHILD":
                    cell_blocks.extend(
                        blocks_by_id[cid]
                        for cid in rel["Ids"]
                        if blocks_by_id.get(cid, {}).get("BlockType") == "CELL"
                    )
            cells = [
                OCRTableCell(
                    text=cell_text(cell),
                    row=cell["RowIndex"] - 1,  # Textract is 1-indexed
                    col=cell["ColumnIndex"] - 1,
                    row_span=cell.get("RowSpan", 1),
                    col_span=cell.get("ColumnSpan", 1),
                    bounding_box=to_bbox(cell),
                    confidence=float(cell.get("Confidence", 0.0)),
                )
                for cell in cell_blocks
            ]
            tables.append(
                OCRTableResult(
                    bounding_box=to_bbox(block),
                    confidence=float(block.get("Confidence", 0.0)),
                    row_count=(max((c.row for c in cells), default=-1) + 1),
                    col_count=(max((c.col for c in cells), default=-1) + 1),
                    cells=cells,
                )
            )
        return tables

    def provider_version(self) -> str:
        try:
            import boto3

            return getattr(boto3, "__version__", "unknown")
        except Exception:  # noqa: BLE001
            return "not installed"

    def supported_languages(self) -> list[str]:
        # Textract's `detect_document_text`/`analyze_document` primarily
        # target English printed/handwritten text; broader language support
        # is more limited than the other five providers — this is AWS's
        # own documented primary-language guidance, not a guess.
        return ["en"]

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            handwriting=True,
            tables=True,
            layout=False,  # no layout/region-classification API distinct from tables/forms
            gpu=False,  # fully managed cloud API
            batch_processing=True,  # async Start*DocumentText/Analysis APIs for multi-page
            multi_page_pdf=True,
            key_value_pairs=True,  # FeatureTypes=["FORMS"]
            selection_marks=True,  # returned as SELECTION_ELEMENT blocks under FORMS/TABLES
            signatures=True,  # FeatureTypes=["SIGNATURES"]
            queries=True,  # FeatureTypes=["QUERIES"]
        )

    def health_check(self) -> HealthCheckResult:
        try:
            import boto3  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            return HealthCheckResult(
                provider_code=self.provider_code,
                installed=False,
                version=None,
                configured=False,
                authenticated=None,
                connectivity=None,
                dependencies_ok=False,
                gpu_available=None,
                ready=False,
                detail=f"boto3 not installed: {exc}",
            )

        configured = bool(self.region)
        detail = None
        if not configured:
            detail = "AWS_TEXTRACT_REGION not configured."
        elif not (self.access_key_id and self.secret_access_key):
            detail = (
                "No explicit AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY configured — relying on "
                "boto3's standard credential chain (IAM role, ~/.aws/credentials, env vars), "
                "which is not verified here."
            )

        return HealthCheckResult(
            provider_code=self.provider_code,
            installed=True,
            version=self.provider_version(),
            configured=configured,
            authenticated=None,  # unknown until a real API call is made
            connectivity=None,
            dependencies_ok=True,
            gpu_available=None,
            ready=configured,
            detail=detail,
        )


def _union_box(boxes: list[BoundingBox]) -> BoundingBox:
    left = min(b.left for b in boxes)
    top = min(b.top for b in boxes)
    right = max(b.left + b.width for b in boxes)
    bottom = max(b.top + b.height for b in boxes)
    return BoundingBox(left=left, top=top, width=right - left, height=bottom - top)
