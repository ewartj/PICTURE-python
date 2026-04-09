"""
prepressr — Jinja2-based report template preprocessor.

Allows parameterised template files to be rendered individually and then
assembled into a combined document (e.g. a multi-section HTML report).

This replaces the R prepressr package which extended Bookdown to support
per-file parameters and repeated inclusion of the same Rmd template.

Key differences from R version:
  - Templates are Jinja2 (.html.j2 or .md.j2) instead of RMarkdown (.Rmd)
  - Output is HTML or Markdown strings (not Bookdown chapters)
  - No chunk-name deduplication needed (that was an Rmd/knitr concern)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, StrictUndefined

logger = logging.getLogger(__name__)


def prepress(
    templates: list[dict[str, Any]],
    template_dir: str | Path,
    output_format: str = "html",
) -> str:
    """Render and concatenate a list of parameterised templates.

    Each entry in *templates* is a dict with:
      - ``"file"``:   template filename relative to *template_dir*
      - ``"params"``: dict of template variables (optional)
      - ``"section_title"``: optional section heading to prepend

    Args:
        templates:    List of template specs to render in order.
        template_dir: Directory containing Jinja2 template files.
        output_format: ``"html"`` or ``"markdown"``.

    Returns:
        Rendered document as a single string.

    Example::

        prepress(
            templates=[
                {"file": "frequency.html.j2", "params": {"title": "Diagnoses"}},
                {"file": "distribution.html.j2", "params": {"title": "Age"}},
            ],
            template_dir="core/prepressr/templates",
        )
    """
    template_dir = Path(template_dir)
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        undefined=StrictUndefined,
        autoescape=(output_format == "html"),
    )

    sections: list[str] = []
    for spec in templates:
        filename = spec["file"]
        params = spec.get("params", {})
        title = spec.get("section_title")

        logger.debug(
            "prepress: rendering %s with params=%s", filename, list(params.keys())
        )
        try:
            tmpl = env.get_template(filename)
            rendered = tmpl.render(**params)
        except Exception as exc:
            logger.error("prepress: failed to render %s: %s", filename, exc)
            raise

        if title:
            rendered = generate_section_header(title, output_format) + rendered

        sections.append(rendered)

    separator = "\n\n" if output_format == "markdown" else "\n"
    return separator.join(sections)


def generate_section_header(title: str, output_format: str = "html") -> str:
    """Generate a section heading string.

    Replaces R ``generate_section_rmd()``.

    Args:
        title:         Section heading text.
        output_format: ``"html"`` or ``"markdown"``.

    Returns:
        Heading string appropriate for the output format.
    """
    if output_format == "markdown":
        return f"## {title}\n\n"
    return f"<h2>{title}</h2>\n"
