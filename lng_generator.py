"""
IFS .lng File Generator
Generates language files with proper CS/CE block structure.
Existing files are parsed and merged so repeated runs extend the output
without duplicating Logical Unit -> View -> Column paths.
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

        for lu_data in data["logical_units"].values():
            lines.extend(self._generate_lu_block(lu_data, indent_level=0))

        return "".join(lines)

    def _generate_lu_block(
        self,
        lu_data: Dict[str, Any],
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a Logical Unit."""
        lines: List[str] = []
        indent = "\t" * indent_level

        lu_name = lu_data["name"]
        lines.append(f"{indent}CS:{lu_name}^LU^Logical Unit^N^N\r\n")

        lu_label = lu_data["label"]
        lines.append(f"{indent}\tA:Prompt^{lu_label}^\r\n")

        for view_data in lu_data["views"].values():
            lines.extend(
                self._generate_view_block(
                    view_data,
                    indent_level + 1,
                )
            )

        lines.append(f"{indent}CE:\r\n")
        return lines

    def _generate_view_block(
        self,
        view_data: Dict[str, Any],
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a View."""
        lines: List[str] = []
        indent = "\t" * indent_level

        view_control = view_data["control"]
        lines.append(f"{indent}CS:{view_control}^LU^View^N^N\r\n")

        for col_data in view_data["columns"].values():
            if col_data.get("is_custom", False):
                lines.extend(
                    self._generate_column_block(
                        col_data,
                        indent_level + 1,
                    )
                )

        lines.append(f"{indent}CE:\r\n")
        return lines

    def _generate_column_block(
        self,
        col_data: Dict[str, Any],
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a Column."""
        lines: List[str] = []
        indent = "\t" * indent_level

        col_control = col_data["control"]
        lines.append(f"{indent}CS:{col_control}^LU^Column^N^N\r\n")

        col_label = col_data["label"]
        lines.append(f"{indent}\tA:Prompt^{col_label}^\r\n")

        lines.append(f"{indent}CE:\r\n")
        return lines

    def generate_file(
        self,
        data: Dict[str, Any],
        output_path: str,
    ) -> str:
        """
        Generate complete .lng file.

        The target file is rewritten from the already merged data structure.

        Args:
            data: Parsed, filtered and merged data structure.
            output_path: Path to write the file.

        Returns:
            Path to generated file.
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

        A duplicate is identified by the complete path:
            Logical Unit -> View -> Column

        Existing entries are retained. Only missing Logical Units, Views
        and Columns are added.

        Args:
            new_data: Data extracted from the current XML file.
            existing_file: Path to an already existing .lng file.

        Returns:
            Merged data structure.
        """
        existing_path = Path(existing_file)

        if not existing_path.exists():
            return deepcopy(new_data)

        existing_data = self._parse_existing_file(existing_path)

        if not existing_data["logical_units"]:
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

        merged_logical_units = merged_data.setdefault(
            "logical_units",
            {},
        )

        for lu_id, new_lu_data in new_data.get(
            "logical_units",
            {},
        ).items():
            if lu_id not in merged_logical_units:
                merged_logical_units[lu_id] = deepcopy(new_lu_data)
                continue

            existing_lu_data = merged_logical_units[lu_id]

            if not existing_lu_data.get("name"):
                existing_lu_data["name"] = new_lu_data.get("name", lu_id)

            if not existing_lu_data.get("label"):
                existing_lu_data["label"] = new_lu_data.get(
                    "label",
                    existing_lu_data["name"],
                )

            existing_views = existing_lu_data.setdefault("views", {})

            for view_id, new_view_data in new_lu_data.get(
                "views",
                {},
            ).items():
                if view_id not in existing_views:
                    existing_views[view_id] = deepcopy(new_view_data)
                    continue

                existing_view_data = existing_views[view_id]

                if not existing_view_data.get("control"):
                    existing_view_data["control"] = new_view_data.get(
                        "control",
                        view_id,
                    )

                if not existing_view_data.get("label"):
                    existing_view_data["label"] = new_view_data.get(
                        "label",
                        existing_view_data["control"],
                    )

                existing_columns = existing_view_data.setdefault(
                    "columns",
                    {},
                )

                for column_id, new_column_data in new_view_data.get(
                    "columns",
                    {},
                ).items():
                    if column_id not in existing_columns:
                        existing_columns[column_id] = deepcopy(
                            new_column_data
                        )

        return merged_data

    def _parse_existing_file(
        self,
        existing_file: Path,
    ) -> Dict[str, Any]:
        """
        Parse an existing .lng file into the internal data structure.

        The parser uses the CS node type stored in the line itself and
        therefore does not depend only on indentation.
        """
        data: Dict[str, Any] = {
            "module": self.module,
            "layer": self.layer,
            "logical_units": {},
        }

        with open(
            existing_file,
            "r",
            encoding="utf-8-sig",
        ) as file:
            lines = file.read().splitlines()

        current_lu_id = None
        current_view_id = None
        current_column_id = None

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
                node_type = parts[2].strip() if len(parts) > 2 else ""

                if not control:
                    continue

                if node_type == "Logical Unit":
                    current_lu_id = control
                    current_view_id = None
                    current_column_id = None

                    data["logical_units"].setdefault(
                        current_lu_id,
                        {
                            "name": control,
                            "label": control,
                            "views": {},
                        },
                    )

                elif node_type == "View" and current_lu_id:
                    current_view_id = control
                    current_column_id = None

                    data["logical_units"][
                        current_lu_id
                    ]["views"].setdefault(
                        current_view_id,
                        {
                            "control": control,
                            "label": control,
                            "columns": {},
                        },
                    )

                elif (
                    node_type == "Column"
                    and current_lu_id
                    and current_view_id
                ):
                    current_column_id = control

                    data["logical_units"][
                        current_lu_id
                    ]["views"][
                        current_view_id
                    ]["columns"].setdefault(
                        current_column_id,
                        {
                            "control": control,
                            "label": control,
                            "is_custom": control.startswith("C_"),
                        },
                    )

                continue

            if line.startswith("A:Prompt^"):
                prompt_parts = line.split("^")
                label = prompt_parts[1] if len(prompt_parts) > 1 else ""

                if (
                    current_lu_id
                    and current_view_id
                    and current_column_id
                ):
                    data["logical_units"][
                        current_lu_id
                    ]["views"][
                        current_view_id
                    ]["columns"][
                        current_column_id
                    ]["label"] = label

                elif current_lu_id and current_view_id is None:
                    data["logical_units"][
                        current_lu_id
                    ]["label"] = label

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
        return f"{module_formatted}_LU_LogicalUnit-{layer}.lng"


if __name__ == "__main__":
    test_data = {
        "module": "ESSPRO",
        "layer": "Cust",
        "logical_units": {
            "TestLU": {
                "name": "TestLU",
                "label": "Test Logical Unit",
                "views": {
                    "TEST_VIEW": {
                        "control": "TEST_VIEW",
                        "label": "Test View",
                        "columns": {
                            "C_TEST_FIELD": {
                                "control": "C_TEST_FIELD",
                                "label": "Test Field",
                                "is_custom": True,
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
