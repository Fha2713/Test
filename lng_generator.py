"""IFS .lng generator with recursive WEB and LU support."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


Node = Dict[str, Any]
Data = Dict[str, Any]


class LNGGenerator:
    """Generate and merge IFS Foundation language files."""

    def __init__(
        self,
        module: str,
        layer: str,
        main_type: str = "LU",
        sub_type: Optional[str] = None,
    ):
        self.module = module
        self.layer = layer
        self.main_type = main_type or "LU"
        self.sub_type = sub_type or ("All" if self.main_type.upper() == "WEB" else "Logical Unit")

    def generate_header(self) -> str:
        header = [
            "-------------------------------------------------------",
            "File Type: IFS Foundation Language File",
            "Type version: 10.00",
            "-------------------------------------------------------",
            f"Module: {self.module}",
            f"Layer: {self.layer}",
            f"Main Type: {self.main_type}",
            f"Sub Type: {self.sub_type}",
            "Content: ",
            "-------------------------------------------------------",
        ]
        return "\r\n".join(header) + "\r\n"

    def generate_content(self, data: Data) -> str:
        lines: List[str] = []
        for node in self._get_resources(data):
            lines.extend(self._generate_node(node, indent_level=0))
        return "".join(lines)

    def _generate_node(self, node: Node, indent_level: int) -> List[str]:
        indent = "\t" * indent_level
        cs_key = node.get("cs_key") or node.get("control") or node.get("id") or ""
        node_type = node.get("type") or node.get("subtype") or "Resource"
        lines = [f"{indent}CS:{cs_key}^{self.main_type}^{node_type}^N^N\r\n"]

        if node.get("emit_label") and node.get("label", ""):
            attribute_key = node.get("attribute_key") or (
                "Prompt" if self.main_type.upper() == "LU" else node.get("control") or cs_key
            )
            lines.append(f"{indent}\tA:{attribute_key}^{node['label']}^\r\n")

        for child in node.get("children", []):
            lines.extend(self._generate_node(child, indent_level + 1))

        lines.append(f"{indent}CE:\r\n")
        return lines

    @staticmethod
    def _get_resources(data: Data) -> List[Node]:
        if "resources" in data:
            return data.get("resources", [])
        # Compatibility with the original fixed LU data model.
        return LNGGenerator._legacy_to_resources(data)

    @staticmethod
    def _legacy_to_resources(data: Data) -> List[Node]:
        resources: List[Node] = []
        for lu_data in data.get("logical_units", {}).values():
            lu = {
                "id": lu_data.get("id", lu_data.get("name", "")),
                "cs_key": lu_data.get("name", ""),
                "control": lu_data.get("name", ""),
                "type": "Logical Unit",
                "label": lu_data.get("label", ""),
                "attribute_key": "Prompt",
                "emit_label": bool(lu_data.get("label")),
                "emit_translation": False,
                "children": [],
            }
            for view_data in lu_data.get("views", {}).values():
                view = {
                    "id": view_data.get("id", view_data.get("control", "")),
                    "cs_key": view_data.get("control", ""),
                    "control": view_data.get("control", ""),
                    "type": "View",
                    "label": "",
                    "attribute_key": "Prompt",
                    "emit_label": False,
                    "emit_translation": False,
                    "children": [],
                }
                for col_data in view_data.get("columns", {}).values():
                    if not col_data.get("is_custom", True):
                        continue
                    view["children"].append(
                        {
                            "id": col_data.get("id", col_data.get("control", "")),
                            "cs_key": col_data.get("control", ""),
                            "control": col_data.get("control", ""),
                            "type": "Column",
                            "label": col_data.get("label", ""),
                            "attribute_key": "Prompt",
                            "emit_label": True,
                            "emit_translation": True,
                            "children": [],
                        }
                    )
                if view["children"]:
                    lu["children"].append(view)
            if lu["children"]:
                resources.append(lu)
        return resources

    def generate_file(self, data: Data, output_path: str) -> str:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        full_content = self.generate_header() + self.generate_content(data)
        with open(output_file, "w", encoding="utf-8", newline="") as handle:
            handle.write(full_content)
        return str(output_file)

    def merge_with_existing(self, new_data: Data, existing_file: str) -> Data:
        existing_path = Path(existing_file)
        if not existing_path.exists():
            return new_data

        existing_data = self._parse_existing_file(existing_path)
        self._validate_merge_metadata(existing_data, new_data)

        merged = existing_data
        merged["version"] = new_data.get("version", merged.get("version", ""))
        self._merge_node_lists(merged["resources"], self._get_resources(new_data))
        merged["logical_units"] = {node["cs_key"]: node for node in merged["resources"]}
        return merged

    def _validate_merge_metadata(self, existing: Data, new: Data) -> None:
        checks = (
            ("module", "modules"),
            ("layer", "layers"),
            ("main_type", "main types"),
        )
        for key, description in checks:
            old_value = str(existing.get(key) or existing.get("type") or "")
            new_value = str(new.get(key) or new.get("type") or "")
            if old_value.casefold() != new_value.casefold():
                raise ValueError(
                    f"Cannot merge different {description}: {old_value!r} and {new_value!r}"
                )

    def _merge_node_lists(self, existing_nodes: List[Node], new_nodes: Iterable[Node]) -> None:
        index = {self._node_identity(node): node for node in existing_nodes}
        for new_node in new_nodes:
            identity = self._node_identity(new_node)
            existing_node = index.get(identity)
            if existing_node is None:
                copied = deepcopy(new_node)
                existing_nodes.append(copied)
                index[identity] = copied
                continue

            if not existing_node.get("label") and new_node.get("label"):
                existing_node["label"] = new_node["label"]
                existing_node["attribute_key"] = new_node.get("attribute_key")
                existing_node["emit_label"] = new_node.get("emit_label", True)
                existing_node["emit_translation"] = new_node.get("emit_translation", True)
            self._merge_node_lists(
                existing_node.setdefault("children", []), new_node.get("children", [])
            )

    @staticmethod
    def _node_identity(node: Node) -> Tuple[str, str]:
        return (
            str(node.get("cs_key", "")).casefold(),
            str(node.get("type", node.get("subtype", ""))).casefold(),
        )

    def _parse_existing_file(self, existing_file: Path) -> Data:
        lines = existing_file.read_text(encoding="utf-8-sig").splitlines()
        headers = self.read_header(existing_file)
        main_type = headers.get("Main Type", self.main_type)
        data: Data = {
            "type": main_type,
            "main_type": main_type,
            "sub_type": headers.get("Sub Type", self.sub_type),
            "module": headers.get("Module", self.module),
            "layer": headers.get("Layer", self.layer),
            "version": "",
            "resources": [],
        }
        stack: List[Node] = []

        for raw_line in lines:
            stripped = raw_line.strip()
            if stripped.startswith("CS:"):
                parts = stripped[3:].split("^")
                cs_key = parts[0].strip()
                node_main_type = parts[1].strip() if len(parts) > 1 else main_type
                node_type = parts[2].strip() if len(parts) > 2 else "Resource"
                parent_id = stack[-1]["id"] if stack else ""
                node_id = f"{parent_id}.{cs_key}" if parent_id else cs_key
                node: Node = {
                    "id": node_id,
                    "name": cs_key if not stack else "",
                    "control": cs_key.rsplit(".", 1)[-1],
                    "cs_key": cs_key,
                    "type": node_type,
                    "subtype": node_type,
                    "label": "",
                    "attribute_key": "Prompt" if node_main_type.upper() == "LU" else cs_key.rsplit(".", 1)[-1],
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

            if stripped.startswith("A:") and stack:
                attribute, value = self._parse_attribute_line(stripped)
                if attribute is not None:
                    stack[-1]["attribute_key"] = attribute
                    stack[-1]["label"] = value
                    stack[-1]["emit_label"] = True
                    stack[-1]["emit_translation"] = (
                        main_type.upper() == "WEB"
                        or stack[-1].get("type", "").casefold() in {"column", "data field"}
                    )

        data["logical_units"] = {node["cs_key"]: node for node in data["resources"]}
        return data

    @staticmethod
    def _parse_attribute_line(line: str) -> Tuple[Optional[str], str]:
        body = line[2:]
        if "^" not in body:
            return None, ""
        attribute, remainder = body.split("^", 1)
        value = remainder[:-1] if remainder.endswith("^") else remainder
        return attribute, value

    @staticmethod
    def read_header(file_path: Path) -> Dict[str, str]:
        result: Dict[str, str] = {}
        with open(file_path, "r", encoding="utf-8-sig") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped.startswith("CS:"):
                    break
                if ":" in stripped:
                    key, value = stripped.split(":", 1)
                    if key in {"Module", "Layer", "Main Type", "Sub Type", "Language", "Culture"}:
                        result[key] = value.strip()
        return result

    def get_file_name(self, module: str, layer: str) -> str:
        module_formatted = module.capitalize()
        if self.main_type.upper() == "WEB":
            return f"{module_formatted}_WEB-{layer}.lng"
        sub_type_compact = self.sub_type.replace(" ", "")
        return f"{module_formatted}_{self.main_type}_{sub_type_compact}-{layer}.lng"
