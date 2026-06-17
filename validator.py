"""Validator for IFS .lng and .trs files."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
import re


class IFSValidator:
    """Validate headers, recursive CS/CE blocks and attribute lines."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_file(self, file_path: str) -> Tuple[bool, List[str], List[str]]:
        self.errors = []
        self.warnings = []
        path = Path(file_path)
        if not path.exists():
            return False, [f"File does not exist: {path}"], []

        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except Exception as exc:
            return False, [f"Failed to read file: {exc}"], []

        is_lng = path.suffix.lower() == ".lng"
        is_trs = path.suffix.lower() == ".trs"
        if not (is_lng or is_trs):
            return False, [f"Unknown file type: {path.suffix}"], []

        self._validate_header(lines, is_lng)
        content_start = self._find_content_start(lines)
        if content_start is None:
            self.errors.append("Could not find content section")
            return False, self.errors, self.warnings

        content = lines[content_start:]
        self._validate_blocks(content, content_start)
        self._validate_indentation(content, content_start)
        self._validate_line_formats(content, content_start, is_lng)
        return not self.errors, self.errors, self.warnings

    def _validate_header(self, lines: List[str], is_lng: bool) -> None:
        header_text = "\n".join(lines[:20])
        expected = "IFS Foundation Language File" if is_lng else "IFS Foundation Translation File"
        if expected not in header_text:
            self.errors.append(f"Invalid file type header. Expected: {expected}")
        if "Type version: 10.00" not in header_text:
            self.warnings.append("Type version is not 10.00")
        for field in ("Module:", "Layer:", "Main Type:", "Sub Type:"):
            if field not in header_text:
                self.errors.append(f"Missing required header field: {field}")
        if not is_lng:
            for field in ("Language:", "Culture:"):
                if field not in header_text:
                    self.errors.append(f"Missing required header field: {field}")

    @staticmethod
    def _find_content_start(lines: List[str]) -> Optional[int]:
        for index, line in enumerate(lines):
            if line.strip().startswith("CS:"):
                return index
        return None

    def _validate_blocks(self, lines: List[str], offset: int) -> None:
        stack: List[Tuple[str, int, int]] = []
        for index, raw_line in enumerate(lines):
            line_no = offset + index + 1
            stripped = raw_line.strip()
            indent = len(raw_line) - len(raw_line.lstrip("\t"))
            if stripped.startswith("CS:"):
                match = re.match(r"CS:([^^]+)", stripped)
                if not match:
                    self.errors.append(f"Line {line_no}: Malformed CS line")
                    continue
                if indent != len(stack):
                    self.errors.append(
                        f"Line {line_no}: CS indentation {indent} does not match nesting level {len(stack)}"
                    )
                stack.append((match.group(1), line_no, indent))
            elif stripped == "CE:":
                if not stack:
                    self.errors.append(f"Line {line_no}: CE without matching CS")
                    continue
                expected_indent = len(stack) - 1
                if indent != expected_indent:
                    self.errors.append(
                        f"Line {line_no}: CE indentation {indent} does not match nesting level {expected_indent}"
                    )
                stack.pop()
        for identifier, line_no, _ in stack:
            self.errors.append(f"Line {line_no}: CS '{identifier}' not closed with CE")

    def _validate_indentation(self, lines: List[str], offset: int) -> None:
        for index, raw_line in enumerate(lines):
            if not raw_line.strip():
                continue
            if raw_line.startswith(" "):
                self.warnings.append(
                    f"Line {offset + index + 1}: Uses spaces instead of tabs for indentation"
                )

    def _validate_line_formats(self, lines: List[str], offset: int, is_lng: bool) -> None:
        for index, raw_line in enumerate(lines):
            line_no = offset + index + 1
            stripped = raw_line.strip()
            if stripped.startswith("CS:"):
                parts = stripped.split("^")
                expected = 5 if is_lng else 2
                if len(parts) != expected:
                    self.errors.append(
                        f"Line {line_no}: Invalid CS format. Expected {expected} parts, got {len(parts)}"
                    )
            elif stripped.startswith(("A:", "P:")):
                if not stripped.endswith("^"):
                    self.errors.append(f"Line {line_no}: Attribute line should end with ^")
                if "^" not in stripped:
                    self.errors.append(f"Line {line_no}: Malformed attribute line")

    def validate_hierarchy(self, file_path: str) -> bool:
        valid, _, _ = self.validate_file(file_path)
        return valid

    def get_summary(self) -> str:
        return f"Validation: {len(self.errors)} errors, {len(self.warnings)} warnings"
