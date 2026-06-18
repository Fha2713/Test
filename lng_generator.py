"""
IFS .lng File Generator
Generates language files with proper CS/CE block structure.
Existing files are parsed and merged so repeated runs extend the output
without duplicating resource paths.
"""

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


class LNGGenerator:
    """Generator for IFS .lng language files."""

    def __init__(
        self,
        module: str,
        layer: str,
        main_type: str = "LU",
        sub_type: str = "Logical Unit",
    ):
        self.module = module
        self.layer = layer
        self.main_type = main_type
        self.sub_type = sub_type

    def generate_header(self) -> str:
        """Generate .lng file header."""
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

    def generate_content(self, data: Dict[str, Any]) -> str:
        """
        Generate complete .lng file content.

        Args:
            data: Parsed and filtered data structure.

        Returns:
            Complete .lng file content as string.
        """
        lines: List[str] = []

        for resource_data in data["translatable_resources"].values():
            lines.extend(self._generate_translatable_resource_block(resource_data, indent_level=0))

        return "".join(lines)

    def _generate_translatable_resource_block(
        self,
        resource_data: Dict[str, Any],
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a top-level TranslatableResource."""
        lines: List[str] = []
        indent = "\t" * indent_level

        resource_name = resource_data["name"]
        resource_type = resource_data.get("type") or self.sub_type
        lines.append(f"{indent}CS:{resource_name}^{self.main_type}^{resource_type}^N^N\r\n")

        resource_label = resource_data.get("label", "")
        if resource_label:
            lines.append(f"{indent}\tA:Prompt^{resource_label}^\r\n")

        for nested_resource_data in resource_data.get("nested_resources", {}).values():
            lines.extend(
                self._generate_nested_resource_block(
                    nested_resource_data,
                    indent_level + 1,
                )
            )

        lines.append(f"{indent}CE:\r\n")
        return lines

    def _generate_nested_resource_block(
        self,
        resource_data: Dict[str, Any],
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a nested Resource."""
        lines: List[str] = []
        indent = "\t" * indent_level

        resource_control = resource_data["control"]
        resource_type = resource_data.get("subtype") or "Resource"
        lines.append(f"{indent}CS:{resource_control}^{self.main_type}^{resource_type}^N^N\r\n")

        resource_label = resource_data.get("label", "")
        if resource_label and resource_data.get("is_custom", False):
            lines.append(f"{indent}\tA:Prompt^{resource_label}^\r\n")

        for nested_resource_data in resource_data.get("nested_resources", {}).values():
            lines.extend(
                self._generate_nested_resource_block(
                    nested_resource_data,
                    indent_level + 1,
                )
            )

        lines.append(f"{indent}CE:\r\n")
        return lines

    def _generate_lu_block(
        self,
        resource_data: Dict[str, Any],
        indent_level: int,
    ) -> List[str]:
        """Backward-compatible wrapper for old method name."""
        return self._generate_translatable_resource_block(resource_data, indent_level)

    def _generate_view_block(
        self,
        resource_data: Dict[str, Any],
        indent_level: int,
    ) -> List[str]:
        """Backward-compatible wrapper for old method name."""
        return self._generate_nested_resource_block(resource_data, indent_level)

    def _generate_column_block(
        self,
        resource_data: Dict[str, Any],
        indent_level: int,
    ) -> List[str]:
        """Backward-compatible wrapper for old method name."""
        return self._generate_nested_resource_block(resource_data, indent_level)

    def generate_file(
        self,
        data: Dict[str, Any],
        output_path: str,
    ) -> str:
        """
        Generate complete .lng file.

        The target file is rewritten from the already merged data structure.
        """
        header = self.generate_header()
        content = self.generate_content(data)
        full_content = header + content

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(
            output_file,
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            file.write(full_content)

        return str(output_file)

    def merge_with_existing(
        self,
        new_data: Dict[str, Any],
        existing_file: str,
    ) -> Dict[str, Any]:
        """
        Merge new XML data with an existing .lng file.

        A duplicate is identified by the complete resource path.
        Existing entries are retained. Only missing resources are added.
        """
        existing_path = Path(existing_file)

        if not existing_path.exists():
            return deepcopy(new_data)

        existing_data = self._parse_existing_file(existing_path)

        if not existing_data["translatable_resources"]:
            return deepcopy(new_data)

        return self._merge_data(existing_data, new_data)

    def _merge_data(
        self,
        existing_data: Dict[str, Any],
        new_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge two internal data structures without duplicate paths."""
        merged_data = deepcopy(existing_data)

        existing_module = merged_data.get("module")
        new_module = new_data.get("module")

        if (
            existing_module
            and new_module
            and existing_module.upper() != new_module.upper()
        ):
            raise ValueError(
                "Cannot merge different modules: "
                f"{existing_module} and {new_module}"
            )

        existing_layer = merged_data.get("layer")
        new_layer = new_data.get("layer")

        if (
            existing_layer
            and new_layer
            and existing_layer.lower() != new_layer.lower()
        ):
            raise ValueError(
                "Cannot merge different layers: "
                f"{existing_layer} and {new_layer}"
            )

        merged_data["module"] = new_module or existing_module or self.module
        merged_data["layer"] = new_layer or existing_layer or self.layer

        merged_resources = merged_data.setdefault(
            "translatable_resources",
            {},
        )

        for resource_id, new_resource_data in new_data.get(
            "translatable_resources",
            {},
        ).items():
            if resource_id not in merged_resources:
                merged_resources[resource_id] = deepcopy(new_resource_data)
                continue

            existing_resource_data = merged_resources[resource_id]
            self._merge_resource_data(
                existing_resource_data,
                new_resource_data,
                resource_id,
            )

        return merged_data

    def _merge_resource_data(
        self,
        existing_resource_data: Dict[str, Any],
        new_resource_data: Dict[str, Any],
        resource_id: str,
    ):
        """Merge one resource node recursively."""
        if not existing_resource_data.get("name"):
            existing_resource_data["name"] = new_resource_data.get("name", resource_id)

        if not existing_resource_data.get("control"):
            existing_resource_data["control"] = new_resource_data.get("control")

        if not existing_resource_data.get("label"):
            existing_resource_data["label"] = new_resource_data.get(
                "label",
                existing_resource_data.get("name") or existing_resource_data.get("control") or resource_id,
            )

        if not existing_resource_data.get("type"):
            existing_resource_data["type"] = new_resource_data.get("type")

        if not existing_resource_data.get("subtype"):
            existing_resource_data["subtype"] = new_resource_data.get("subtype")

        existing_resource_data["is_custom"] = (
            existing_resource_data.get("is_custom", False)
            or new_resource_data.get("is_custom", False)
        )

        existing_nested_resources = existing_resource_data.setdefault(
            "nested_resources",
            {},
        )

        for nested_resource_id, new_nested_resource_data in new_resource_data.get(
            "nested_resources",
            {},
        ).items():
            if nested_resource_id not in existing_nested_resources:
                existing_nested_resources[nested_resource_id] = deepcopy(new_nested_resource_data)
                continue

            self._merge_resource_data(
                existing_nested_resources[nested_resource_id],
                new_nested_resource_data,
                nested_resource_id,
            )

    def _parse_existing_file(
        self,
        existing_file: Path,
    ) -> Dict[str, Any]:
        """
        Parse an existing .lng file into the internal data structure.

        The parser uses indentation only for hierarchy depth and keeps all
        resource types from the CS line.
        """
        data: Dict[str, Any] = {
            "type": self.main_type,
            "sub_type": self.sub_type,
            "module": self.module,
            "layer": self.layer,
            "translatable_resources": {},
        }

        with open(
            existing_file,
            "r",
            encoding="utf-8-sig",
        ) as file:
            lines = file.read().splitlines()

        resource_stack: List[Dict[str, Any]] = []

        for raw_line in lines:
            line = raw_line.strip()

            if line.startswith("Module:"):
                data["module"] = line.split(":", 1)[1].strip()
                continue

            if line.startswith("Layer:"):
                data["layer"] = line.split(":", 1)[1].strip()
                continue

            if line.startswith("CS:"):
                parts = line[3:].split("^")
                control = parts[0].strip() if parts else ""
                main_type = parts[1].strip() if len(parts) > 1 else self.main_type
                resource_type = parts[2].strip() if len(parts) > 2 else ""
                indentation = len(raw_line) - len(raw_line.lstrip("\t"))

                if not control:
                    continue

                data["type"] = main_type or data.get("type")

                if indentation == 0:
                    data["sub_type"] = resource_type or self.sub_type
                    resource_data = data["translatable_resources"].setdefault(
                        control,
                        {
                            "name": control,
                            "type": resource_type or self.sub_type,
                            "label": control,
                            "nested_resources": {},
                        },
                    )
                else:
                    parent_data = resource_stack[indentation - 1]
                    resource_data = parent_data.setdefault(
                        "nested_resources",
                        {},
                    ).setdefault(
                        control,
                        {
                            "control": control,
                            "subtype": resource_type or "Resource",
                            "label": control,
                            "is_custom": control.startswith("C_"),
                            "nested_resources": {},
                        },
                    )

                if len(resource_stack) <= indentation:
                    resource_stack.append(resource_data)
                else:
                    resource_stack[indentation] = resource_data
                    del resource_stack[indentation + 1:]

                continue

            if line.startswith("A:Prompt^"):
                prompt_parts = line.split("^")
                label = prompt_parts[1] if len(prompt_parts) > 1 else ""
                indentation = len(raw_line) - len(raw_line.lstrip("\t"))
                resource_indent = max(indentation - 1, 0)

                if len(resource_stack) > resource_indent:
                    resource_stack[resource_indent]["label"] = label

        return data

    def get_file_name(
        self,
        module: str,
        layer: str,
    ) -> str:
        """
        Get standard file name for .lng file.

        Example:
            Esspro_LU_LogicalUnit-Cust.lng
        """
        module_formatted = module.capitalize()
        sub_type_formatted = "".join((self.sub_type or "").split())
        return f"{module_formatted}_{self.main_type}_{sub_type_formatted}-{layer}.lng"


if __name__ == "__main__":
    test_data = {
        "module": "ESSPRO",
        "layer": "Cust",
        "translatable_resources": {
            "TestLU": {
                "name": "TestLU",
                "label": "Test Logical Unit",
                "nested_resources": {
                    "TEST_VIEW": {
                        "control": "TEST_VIEW",
                        "label": "Test View",
                        "nested_resources": {
                            "C_TEST_FIELD": {
                                "control": "C_TEST_FIELD",
                                "label": "Test Field",
                                "is_custom": True,
                                "nested_resources": {},
                            }
                        },
                    }
                },
            }
        },
    }

    generator = LNGGenerator("ESSPRO", "Cust")
    content = generator.generate_header() + generator.generate_content(
        test_data
    )
    print(content)
