"""IFS .trs generator with recursive WEB and LU support."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from lng_generator import LNGGenerator


Node = Dict[str, Any]
Data = Dict[str, Any]


class TRSGenerator:
    """Generate/merge IFS translation files without expanding unrelated LNG data."""

    LANGUAGES = {
        "sv-SE": {"code": "sv", "name": "Swedish"},
        "nb-NO": {"code": "no", "name": "Norwegian"},
        "de-DE": {"code": "de", "name": "German"},
    }

    def __init__(
        self,
        module: str,
        layer: str,
        language: str,
        main_type: str = "LU",
        sub_type: Optional[str] = None,
    ):
        self.module = module
        self.layer = layer
        self.language = language
        self.main_type = main_type or "LU"
        self.sub_type = sub_type or ("All" if self.main_type.upper() == "WEB" else "Logical Unit")
        mapping = self.LANGUAGES.get(language, {})
        self.lang_code = mapping.get("code", language.split("-", 1)[0])
        self.culture = language

    def generate_header(self) -> str:
        header = [
            "-------------------------------------------------------",
            "File Type: IFS Foundation Translation File",
            "Type version: 10.00",
            "-------------------------------------------------------",
            f"Module: {self.module}",
            f"Language: {self.lang_code}",
            f"Culture: {self.culture}",
            f"Layer: {self.layer}",
            f"Main Type: {self.main_type}",
            f"Sub Type: {self.sub_type}",
            "Content: ",
            "-------------------------------------------------------",
        ]
        return "\r\n".join(header) + "\r\n"

    def generate_content(self, data: Data, translations: Dict[str, str]) -> str:
        lines: List[str] = []
        for node in LNGGenerator._get_resources(data):
            lines.extend(self._generate_node(node, translations, indent_level=0))
        return "".join(lines)

    def _generate_node(
        self,
        node: Node,
        translations: Dict[str, str],
        indent_level: int,
    ) -> List[str]:
        indent = "\t" * indent_level
        cs_key = node.get("cs_key") or node.get("control") or node.get("id") or ""
        lines = [f"{indent}CS:{cs_key}^{self.main_type}\r\n"]

        if node.get("emit_translation") and node.get("label", ""):
            original = node["label"]
            attribute_key = node.get("attribute_key") or (
                "Prompt" if self.main_type.upper() == "LU" else node.get("control") or cs_key
            )
            translated = node.get("translated_label")
            if translated is None:
                translated = translations.get(original, original)
            lines.append(f"{indent}\tP:{original}^\r\n")
            lines.append(f"{indent}\tA:{attribute_key}^{translated}^\r\n")

        for child in node.get("children", []):
            lines.extend(self._generate_node(child, translations, indent_level + 1))

        lines.append(f"{indent}CE:\r\n")
        return lines

    def merge_with_existing(
        self,
        new_data: Data,
        translations: Dict[str, str],
        existing_file: str,
    ) -> Data:
        existing_path = Path(existing_file)
        if not existing_path.exists():
            return self._prepare_new_data(new_data, translations)

        existing_data = self._parse_existing_file(existing_path)
        self._validate_merge_metadata(existing_data, new_data)
        self._merge_node_lists(
            existing_data["resources"],
            LNGGenerator._get_resources(new_data),
            translations,
        )
        return existing_data

    def _prepare_new_data(self, new_data: Data, translations: Dict[str, str]) -> Data:
        prepared = deepcopy(new_data)
        for node in LNGGenerator._get_resources(prepared):
            self._apply_new_translations(node, translations)
        return prepared

    def _apply_new_translations(self, node: Node, translations: Dict[str, str]) -> None:
        if node.get("emit_translation") and node.get("label", ""):
            node["translated_label"] = translations.get(node["label"], node["label"])
        for child in node.get("children", []):
            self._apply_new_translations(child, translations)

    def _merge_node_lists(
        self,
        existing_nodes: List[Node],
        new_nodes: Iterable[Node],
        translations: Dict[str, str],
    ) -> None:
        index = {str(node.get("cs_key", "")).casefold(): node for node in existing_nodes}
        for new_node in new_nodes:
            key = str(new_node.get("cs_key", "")).casefold()
            existing_node = index.get(key)
            if existing_node is None:
                copied = deepcopy(new_node)
                self._apply_new_translations(copied, translations)
                existing_nodes.append(copied)
                index[key] = copied
                continue

            # Existing P/A values have priority. Add translation only when the
            # block previously had no translation entry.
            if (
                not existing_node.get("emit_translation")
                and new_node.get("emit_translation")
                and new_node.get("label")
            ):
                existing_node["label"] = new_node["label"]
                existing_node["attribute_key"] = new_node.get("attribute_key")
                existing_node["emit_translation"] = True
                existing_node["translated_label"] = translations.get(
                    new_node["label"], new_node["label"]
                )

            self._merge_node_lists(
                existing_node.setdefault("children", []),
                new_node.get("children", []),
                translations,
            )

    def _parse_existing_file(self, existing_file: Path) -> Data:
        lines = existing_file.read_text(encoding="utf-8-sig").splitlines()
        headers = LNGGenerator.read_header(existing_file)
        main_type = headers.get("Main Type", self.main_type)
        data: Data = {
            "type": main_type,
            "main_type": main_type,
            "sub_type": headers.get("Sub Type", self.sub_type),
            "module": headers.get("Module", self.module),
            "layer": headers.get("Layer", self.layer),
            "culture": headers.get("Culture", self.culture),
            "resources": [],
        }
        stack: List[Node] = []

        for raw_line in lines:
            stripped = raw_line.strip()
            if stripped.startswith("CS:"):
                parts = stripped[3:].split("^")
                cs_key = parts[0].strip()
                parent_id = stack[-1]["id"] if stack else ""
                node: Node = {
                    "id": f"{parent_id}.{cs_key}" if parent_id else cs_key,
                    "name": cs_key if not stack else "",
                    "control": cs_key.rsplit(".", 1)[-1],
                    "cs_key": cs_key,
                    "type": "",
                    "subtype": "",
                    "label": "",
                    "translated_label": None,
                    "attribute_key": "Prompt" if main_type.upper() == "LU" else cs_key.rsplit(".", 1)[-1],
                    "emit_label": False,
                    "emit_translation": False,
                    "children": [],
                }
                if stack:
                    stack[-1]["children"].append(node)
                else:
                    data["resources"].append(node)
                stack.append(node)
                continue

            if stripped == "CE:":
                if stack:
                    stack.pop()
                continue

            if stripped.startswith("P:") and stack:
                stack[-1]["label"] = self._parse_prompt_line(stripped)
                stack[-1]["emit_translation"] = True
                continue

            if stripped.startswith("A:") and stack:
                attribute, value = LNGGenerator._parse_attribute_line(stripped)
                if attribute is not None:
                    stack[-1]["attribute_key"] = attribute
                    stack[-1]["translated_label"] = value
                    stack[-1]["emit_translation"] = True

        return data

    def _validate_merge_metadata(self, existing: Data, new: Data) -> None:
        comparisons = (
            ("module", self.module),
            ("layer", self.layer),
            ("main_type", self.main_type),
            ("culture", self.culture),
        )
        for key, expected in comparisons:
            actual = str(existing.get(key, ""))
            if actual and actual.casefold() != str(expected).casefold():
                raise ValueError(
                    f"Cannot merge TRS with different {key}: {actual!r} and {expected!r}"
                )

    @staticmethod
    def _parse_prompt_line(line: str) -> str:
        value = line[2:]
        return value[:-1] if value.endswith("^") else value

    def read_existing_translations(self, existing_file: str) -> Dict[Tuple[Tuple[str, ...], str], str]:
        """Backward-compatible translation lookup helper."""
        path = Path(existing_file)
        if not path.exists():
            return {}
        data = self._parse_existing_file(path)
        result: Dict[Tuple[Tuple[str, ...], str], str] = {}

        def visit(node: Node, parent: Tuple[str, ...]) -> None:
            current = parent + (node["cs_key"],)
            if node.get("emit_translation") and node.get("translated_label") is not None:
                result[(current, node.get("attribute_key", ""))] = node["translated_label"]
            for child in node.get("children", []):
                visit(child, current)

        for root in data["resources"]:
            visit(root, ())
        return result

    def generate_file(
        self,
        data: Data,
        translations: Dict[str, str],
        output_path: str,
        existing_file: Optional[str] = None,
    ) -> str:
        source = existing_file or (output_path if Path(output_path).exists() else None)
        if source:
            data_to_write = self.merge_with_existing(data, translations, source)
        else:
            data_to_write = self._prepare_new_data(data, translations)

        full_content = self.generate_header() + self.generate_content(data_to_write, translations)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8", newline="") as handle:
            handle.write(full_content)
        return str(output_file)

    def get_file_name(self, module: str, layer: str, language: str) -> str:
        module_formatted = module.capitalize()
        lang_code = self.LANGUAGES.get(language, {}).get("code", language.split("-", 1)[0])
        if self.main_type.upper() == "WEB":
            return f"{module_formatted}_WEB-{layer}-{lang_code}.trs"
        sub_type_compact = self.sub_type.replace(" ", "")
        return f"{module_formatted}_{self.main_type}_{sub_type_compact}-{layer}-{lang_code}.trs"
