"""IFS TranslatableResources XML parser.

Supports both the classic LU hierarchy and arbitrary recursive WEB/Global Data
resource trees. Customisation detection is based on the XML ``ID`` path, not
on ``control``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


Node = Dict[str, Any]
Data = Dict[str, Any]


class IFSXMLParser:
    """Parse and filter IFS ``TranslatableResources`` XML files."""

    NAMESPACE = {"ifs": "types.scan.translation.fnd.ifsworld.com"}

    # ``Dm`` is case-insensitive and may be followed by ``_`` or directly by
    # the remaining identifier. The C prefix is accepted as C_, CName and CDm.
    # The uppercase boundary avoids treating normal identifiers such as
    # ``command``, ``content`` or ``CalendarId`` as custom C resources.
    _DM_PREFIX = re.compile(r"^dm", re.IGNORECASE)
    _C_UNDERSCORE_PREFIX = re.compile(r"^c_", re.IGNORECASE)
    _C_CAMEL_PREFIX = re.compile(r"^[cC](?:[A-Z]|(?i:dm))")

    def __init__(self, xml_path: str):
        self.xml_path = Path(xml_path)
        self.tree: Optional[ET.ElementTree] = None
        self.root: Optional[ET.Element] = None

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    def parse(self) -> Data:
        """Parse the XML into a generic recursive resource tree."""
        self.tree = ET.parse(self.xml_path)
        self.root = self.tree.getroot()

        main_type = (self.root.get("type") or "LU").strip()
        result: Data = {
            "type": main_type,
            "main_type": main_type,
            "sub_type": "All" if main_type.upper() == "WEB" else "Logical Unit",
            "module": (self.root.get("module") or "").strip(),
            "version": (self.root.get("version") or "").strip(),
            "layer": (self.root.get("layer") or "").strip(),
            "resources": [],
        }

        for element in self.root:
            if self._local_name(element.tag) != "TranslatableResource":
                continue
            result["resources"].append(
                self._parse_resource(element, parent_id=None, main_type=main_type, depth=0)
            )

        # Compatibility alias for callers written against the original repo.
        result["logical_units"] = {
            node["cs_key"]: node for node in result["resources"]
        }
        return result

    def _parse_resource(
        self,
        element: ET.Element,
        parent_id: Optional[str],
        main_type: str,
        depth: int,
    ) -> Node:
        element_id = (element.get("ID") or "").strip()
        control = (element.get("control") or "").strip()
        name = (element.get("name") or "").strip()
        resource_type = (
            element.get("subtype")
            or element.get("type")
            or ("Logical Unit" if depth == 0 else "Resource")
        ).strip()

        if depth == 0:
            # The old LU generator used name; WEB examples use the global ID.
            cs_key = name if main_type.upper() == "LU" and name else element_id or name or control
        else:
            cs_key = self._relative_id(element_id, parent_id) or control or element_id

        label = self._get_direct_text(element)
        attribute_key = "Prompt" if main_type.upper() == "LU" else (control or cs_key)
        emit_label = bool(label) and (
            main_type.upper() == "WEB"
            or depth == 0
            or resource_type.casefold() in {"column", "data field"}
        )
        emit_translation = bool(label) and (
            main_type.upper() == "WEB"
            or resource_type.casefold() in {"column", "data field"}
        )

        node: Node = {
            "id": element_id,
            "name": name,
            "control": control,
            "cs_key": cs_key,
            "type": resource_type,
            "subtype": resource_type,
            "label": label,
            "attribute_key": attribute_key,
            "emit_label": emit_label,
            "emit_translation": emit_translation,
            "children": [],
        }

        for child in element:
            if self._local_name(child.tag) != "Resource":
                continue
            node["children"].append(
                self._parse_resource(
                    child,
                    parent_id=element_id,
                    main_type=main_type,
                    depth=depth + 1,
                )
            )
        return node

    @staticmethod
    def _relative_id(element_id: str, parent_id: Optional[str]) -> str:
        if not element_id:
            return ""
        if parent_id:
            prefix = f"{parent_id}."
            if element_id.casefold().startswith(prefix.casefold()):
                return element_id[len(prefix) :]
        return element_id.rsplit(".", 1)[-1]

    def _get_direct_text(self, element: ET.Element) -> str:
        for child in element:
            if self._local_name(child.tag) == "Text":
                return (child.text or "").strip()
        return ""

    @classmethod
    def _segment_has_custom_prefix(cls, segment: str) -> bool:
        segment = segment.strip()
        if not segment:
            return False
        return bool(
            cls._DM_PREFIX.match(segment)
            or cls._C_UNDERSCORE_PREFIX.match(segment)
            or cls._C_CAMEL_PREFIX.match(segment)
        )

    @classmethod
    def id_has_custom_prefix(cls, identifier: str) -> bool:
        """Return True when any ID path segment has a supported prefix."""
        return any(
            cls._segment_has_custom_prefix(segment)
            for segment in re.split(r"[./]", identifier or "")
        )

    def extract_custom_fields(self, parsed_data: Data) -> Data:
        """Filter resources using custom prefixes found in their XML IDs.

        Once a node is custom, its full subtree is retained. When only a deeper
        child is custom, the non-custom ancestors required for the hierarchy are
        retained, while unrelated sibling branches are omitted.
        """
        result: Data = {
            key: deepcopy(value)
            for key, value in parsed_data.items()
            if key not in {"resources", "logical_units"}
        }
        result["resources"] = []

        for node in parsed_data.get("resources", []):
            filtered = self._filter_node(node, ancestor_is_custom=False)
            if filtered is not None:
                result["resources"].append(filtered)

        result["logical_units"] = {
            node["cs_key"]: node for node in result["resources"]
        }
        return result

    # Clearer generic alias for new callers.
    extract_custom_resources = extract_custom_fields

    def _filter_node(self, node: Node, ancestor_is_custom: bool) -> Optional[Node]:
        current_is_custom = ancestor_is_custom or self.id_has_custom_prefix(node.get("id", ""))
        if current_is_custom:
            copied = deepcopy(node)
            copied["is_custom"] = True
            return copied

        filtered_children: List[Node] = []
        for child in node.get("children", []):
            filtered = self._filter_node(child, ancestor_is_custom=False)
            if filtered is not None:
                filtered_children.append(filtered)

        if not filtered_children:
            return None

        copied = deepcopy(node)
        copied["children"] = filtered_children
        copied["is_custom"] = False
        return copied

    @staticmethod
    def iter_nodes(data_or_nodes: Any) -> Iterator[Node]:
        if isinstance(data_or_nodes, dict):
            nodes = data_or_nodes.get("resources", [])
        else:
            nodes = data_or_nodes
        for node in nodes:
            yield node
            yield from IFSXMLParser.iter_nodes(node.get("children", []))

    @staticmethod
    def iter_text_nodes(data: Data, translations_only: bool = False) -> Iterator[Node]:
        flag = "emit_translation" if translations_only else "emit_label"
        for node in IFSXMLParser.iter_nodes(data):
            if node.get(flag) and node.get("label", ""):
                yield node

    def get_statistics(self, parsed_data: Data) -> Dict[str, int]:
        nodes = list(self.iter_nodes(parsed_data))
        text_nodes = [node for node in nodes if node.get("label")]
        custom_text_nodes = [
            node for node in text_nodes if self.id_has_custom_prefix(node.get("id", ""))
        ]
        top_count = len(parsed_data.get("resources", []))
        depth_one_count = sum(len(node.get("children", [])) for node in parsed_data.get("resources", []))
        stats = {
            "total_resources": len(nodes),
            "text_resources": len(text_nodes),
            "custom_resources": len(custom_text_nodes),
            "standard_resources": len(text_nodes) - len(custom_text_nodes),
            # Backward-compatible logger keys.
            "total_logical_units": top_count,
            "total_views": depth_one_count,
            "total_columns": len(text_nodes),
            "custom_columns": len(custom_text_nodes),
            "standard_columns": len(text_nodes) - len(custom_text_nodes),
        }
        return stats


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        parser = IFSXMLParser(sys.argv[1])
        parsed = parser.parse()
        filtered = parser.extract_custom_resources(parsed)
        print(json.dumps(parser.get_statistics(parsed), indent=2))
        print(f"Filtered top-level resources: {len(filtered['resources'])}")
