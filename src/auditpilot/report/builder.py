"""Report builder generating Markdown and standalone single-file HTML reports."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from auditpilot.models import AuditResult


class ReportBuilder:
    """Generates agency-quality Markdown and HTML reports from AuditResult."""

    def __init__(self, result: "AuditResult") -> None:
        self.result = result

    def to_markdown(self) -> str:
        """Render report as clean Markdown string."""
        raise NotImplementedError("Will be implemented in Phase 5")

    def to_html(self) -> str:
        """Render report as standalone single-file styled HTML string."""
        raise NotImplementedError("Will be implemented in Phase 5")

    def save_reports(self, output_dir: Path | str = "./reports") -> tuple[Path, Path]:
        """Save both Markdown and HTML reports to disk.

        Returns:
            Tuple of (md_path, html_path).
        """
        raise NotImplementedError("Will be implemented in Phase 5")
