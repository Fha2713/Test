"""
IFS .trs Translation File Generator
Generates translation files with P: and A:Prompt entries.
Existing translations are preserved when a file is extended in a later run.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple


TranslationPath = Tuple[str, str, str]


class TRSGenerator:
    """Generator for IFS .trs translation files."""

    LANGUAGES = {
        "sv-SE": {"code": "sv", "name": "Swedish"},
        "nb-NO": {"code": "no", "name": "Norwegian"},
    }

    def __init__(
        self,
        module: str,
        layer: str,
        language: str,
        main_type: str = "LU",
        sub_type: str = "Logical Unit",
    ):
        self.module = module
        self.layer = layer
        self.language = language
        self.main_type = main_type
        self.sub_type = sub_type

        if language in self.LANGUAGES:
            self.lang_code = self.LANGUAGES[language]["code"]
            self.culture = language
        else:
            self.lang_code = language.split("-")[0]
            self.culture = language

    def generate_header(self) -> str:
        """Generate .trs file header."""
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

    def generate_content(
        self,
        data: Dict[str, Any],
        translations: Dict[str, str],
        existing_translations: Dict[TranslationPath, str] = None,
    ) -> str:
        """
        Generate complete .trs file content.

        Existing translations are preferred over newly generated values.
        """
        existing_translations = existing_translations or {}
        lines: List[str] = []

        for lu_id, lu_data in data["logical_units"].items():
            lines.extend(
                self._generate_lu_block(
                    lu_id=lu_id,
                    lu_data=lu_data,
                    translations=translations,
                    existing_translations=existing_translations,
                    indent_level=0,
                )
            )

        return "".join(lines)

    def _generate_lu_block(
        self,
        lu_id: str,
        lu_data: Dict[str, Any],
        translations: Dict[str, str],
        existing_translations: Dict[TranslationPath, str],
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a Logical Unit."""
        lines: List[str] = []
        indent = "\t" * indent_level

        lu_name = lu_data["name"]
        lines.append(f"{indent}CS:{lu_name}^LU\r\n")

        for view_id, view_data in lu_data["views"].items():
            lines.extend(
                self._generate_view_block(
                    lu_id=lu_id,
                    view_id=view_id,
                    view_data=view_data,
                    translations=translations,
                    existing_translations=existing_translations,
                    indent_level=indent_level + 1,
                )
            )

        lines.append(f"{indent}CE:\r\n")
        return lines

    def _generate_view_block(
        self,
        lu_id: str,
        view_id: str,
        view_data: Dict[str, Any],
        translations: Dict[str, str],
        existing_translations: Dict[TranslationPath, str],
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a View."""
        lines: List[str] = []
        indent = "\t" * indent_level

        view_control = view_data["control"]
        lines.append(f"{indent}CS:{view_control}^LU\r\n")

        for column_id, col_data in view_data["columns"].items():
            if col_data.get("is_custom", False):
                lines.extend(
                    self._generate_column_block(
                        lu_id=lu_id,
                        view_id=view_id,
                        column_id=column_id,
                        col_data=col_data,
                        translations=translations,
                        existing_translations=existing_translations,
                        indent_level=indent_level + 1,
                    )
                )

        lines.append(f"{indent}CE:\r\n")
        return lines

    def _generate_column_block(
        self,
        lu_id: str,
        view_id: str,
        column_id: str,
        col_data: Dict[str, Any],
        translations: Dict[str, str],
        existing_translations: Dict[TranslationPath, str],
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a Column."""
        lines: List[str] = []
        indent = "\t" * indent_level

        col_control = col_data["control"]
        original_label = col_data["label"]
        translation_path = (lu_id, view_id, column_id)

        translated_label = existing_translations.get(
            translation_path,
            translations.get(original_label, original_label),
        )

        lines.append(f"{indent}CS:{col_control}^LU\r\n")
        lines.append(f"{indent}\tP:{original_label}^\r\n")
        lines.append(f"{indent}\tA:Prompt^{translated_label}^\r\n")
        lines.append(f"{indent}CE:\r\n")

        return lines

    def read_existing_translations(
        self,
        existing_file: str,
    ) -> Dict[TranslationPath, str]:
        """
        Read translations from an existing .trs file.

        The hierarchy in a .trs file does not contain explicit node type
        values. Therefore the parser uses the nesting depth:

            depth 0 = Logical Unit
            depth 1 = View
            depth 2 = Column
        """
        existing_path = Path(existing_file)

        if not existing_path.exists():
            return {}

        translations: Dict[TranslationPath, str] = {}

        with open(
            existing_path,
            "r",
            encoding="utf-8-sig",
        ) as file:
            lines = file.read().splitlines()

        current_lu = None
        current_view = None
        current_column = None

        for raw_line in lines:
            stripped = raw_line.strip()

            if stripped.startswith("CS:"):
                control = stripped[3:].split("^", 1)[0].strip()
                indentation = len(raw_line) - len(raw_line.lstrip("\t"))

                if indentation == 0:
                    current_lu = control
                    current_view = None
                    current_column = None

                elif indentation == 1 and current_lu:
                    current_view = control
                    current_column = None

                elif (
                    indentation == 2
                    and current_lu
                    and current_view
                ):
                    current_column = control

                continue

            if (
                stripped.startswith("A:Prompt^")
                and current_lu
                and current_view
                and current_column
            ):
                prompt_parts = stripped.split("^")
                translated_label = (
                    prompt_parts[1] if len(prompt_parts) > 1 else ""
                )

                translations[
                    (
                        current_lu,
                        current_view,
                        current_column,
                    )
                ] = translated_label

        return translations

    def generate_file(
        self,
        data: Dict[str, Any],
        translations: Dict[str, str],
        output_path: str,
    ) -> str:
        """
        Generate or update a complete .trs file.

        Existing translations are read before the file is rewritten.
        This preserves manual or previously generated translations for
        entries that already exist.
        """
        output_file = Path(output_path)

        existing_translations = self.read_existing_translations(
            str(output_file)
        )

        header = self.generate_header()
        content = self.generate_content(
            data=data,
            translations=translations,
            existing_translations=existing_translations,
        )
        full_content = header + content

        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(
            output_file,
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            file.write(full_content)

        return str(output_file)

    def get_file_name(
        self,
        module: str,
        layer: str,
        language: str,
    ) -> str:
        """
        Get standard file name for .trs file.

        Example:
            Esspro_LU_LogicalUnit-Cust-sv.trs
        """
        module_formatted = module.capitalize()

        if language in self.LANGUAGES:
            lang_code = self.LANGUAGES[language]["code"]
        else:
            lang_code = language.split("-")[0]

        return (
            f"{module_formatted}_LU_LogicalUnit-"
            f"{layer}-{lang_code}.trs"
        )


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

    test_translations = {"Test Field": "Testfält"}

    generator = TRSGenerator("ESSPRO", "Cust", "sv-SE")
    content = generator.generate_header() + generator.generate_content(
        test_data,
        test_translations,
    )
    print(content)
