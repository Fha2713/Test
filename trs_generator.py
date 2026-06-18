"""
IFS .trs Translation File Generator
Generates translation files with P: and A:Prompt entries.
Existing translations are preserved when a file is extended in a later run.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple


TranslationPath = Tuple[str, ...]


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

        for resource_id, resource_data in data["translatable_resources"].items():
            lines.extend(
                self._generate_translatable_resource_block(
                    resource_id=resource_id,
                    resource_data=resource_data,
                    translations=translations,
                    existing_translations=existing_translations,
                    current_path=(resource_id,),
                    indent_level=0,
                )
            )

        return "".join(lines)

    def _generate_translatable_resource_block(
        self,
        resource_id: str,
        resource_data: Dict[str, Any],
        translations: Dict[str, str],
        existing_translations: Dict[TranslationPath, str],
        current_path: TranslationPath,
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a top-level TranslatableResource."""
        lines: List[str] = []
        indent = "\t" * indent_level

        resource_name = resource_data["name"]
        lines.append(f"{indent}CS:{resource_name}^{self.main_type}\r\n")

        for nested_resource_id, nested_resource_data in resource_data.get("nested_resources", {}).items():
            lines.extend(
                self._generate_nested_resource_block(
                    resource_id=nested_resource_id,
                    resource_data=nested_resource_data,
                    translations=translations,
                    existing_translations=existing_translations,
                    current_path=current_path + (nested_resource_id,),
                    indent_level=indent_level + 1,
                )
            )

        lines.append(f"{indent}CE:\r\n")
        return lines

    def _generate_nested_resource_block(
        self,
        resource_id: str,
        resource_data: Dict[str, Any],
        translations: Dict[str, str],
        existing_translations: Dict[TranslationPath, str],
        current_path: TranslationPath,
        indent_level: int,
    ) -> List[str]:
        """Generate CS/CE block for a nested Resource."""
        lines: List[str] = []
        indent = "\t" * indent_level

        resource_control = resource_data["control"]
        lines.append(f"{indent}CS:{resource_control}^{self.main_type}\r\n")

        if resource_data.get("is_custom", False):
            original_label = resource_data.get("label", "")
            translated_label = existing_translations.get(
                current_path,
                translations.get(original_label, original_label),
            )

            lines.append(f"{indent}\tP:{original_label}^\r\n")
            lines.append(f"{indent}\tA:Prompt^{translated_label}^\r\n")

        for nested_resource_id, nested_resource_data in resource_data.get("nested_resources", {}).items():
            lines.extend(
                self._generate_nested_resource_block(
                    resource_id=nested_resource_id,
                    resource_data=nested_resource_data,
                    translations=translations,
                    existing_translations=existing_translations,
                    current_path=current_path + (nested_resource_id,),
                    indent_level=indent_level + 1,
                )
            )

        lines.append(f"{indent}CE:\r\n")
        return lines

    def _generate_lu_block(
        self,
        resource_id: str,
        resource_data: Dict[str, Any],
        translations: Dict[str, str],
        existing_translations: Dict[TranslationPath, str],
        indent_level: int,
    ) -> List[str]:
        """Backward-compatible wrapper for old method name."""
        return self._generate_translatable_resource_block(
            resource_id=resource_id,
            resource_data=resource_data,
            translations=translations,
            existing_translations=existing_translations,
            current_path=(resource_id,),
            indent_level=indent_level,
        )

    def _generate_view_block(
        self,
        parent_resource_id: str,
        nested_resource_id: str,
        nested_resource_data: Dict[str, Any],
        translations: Dict[str, str],
        existing_translations: Dict[TranslationPath, str],
        indent_level: int,
    ) -> List[str]:
        """Backward-compatible wrapper for old method name."""
        return self._generate_nested_resource_block(
            resource_id=nested_resource_id,
            resource_data=nested_resource_data,
            translations=translations,
            existing_translations=existing_translations,
            current_path=(parent_resource_id, nested_resource_id),
            indent_level=indent_level,
        )

    def _generate_column_block(
        self,
        top_resource_id: str,
        parent_resource_id: str,
        nested_resource_id: str,
        nested_resource_data: Dict[str, Any],
        translations: Dict[str, str],
        existing_translations: Dict[TranslationPath, str],
        indent_level: int,
    ) -> List[str]:
        """Backward-compatible wrapper for old method name."""
        return self._generate_nested_resource_block(
            resource_id=nested_resource_id,
            resource_data=nested_resource_data,
            translations=translations,
            existing_translations=existing_translations,
            current_path=(top_resource_id, parent_resource_id, nested_resource_id),
            indent_level=indent_level,
        )

    def read_existing_translations(
        self,
        existing_file: str,
    ) -> Dict[TranslationPath, str]:
        """
        Read translations from an existing .trs file.

        The hierarchy in a .trs file does not contain explicit node type
        values. Therefore the parser uses the nesting depth and supports
        any number of nested resources.
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

        path_stack: List[str] = []

        for raw_line in lines:
            stripped = raw_line.strip()

            if stripped.startswith("CS:"):
                control = stripped[3:].split("^", 1)[0].strip()
                indentation = len(raw_line) - len(raw_line.lstrip("\t"))

                if not control:
                    continue

                if len(path_stack) <= indentation:
                    path_stack.append(control)
                else:
                    path_stack[indentation] = control
                    del path_stack[indentation + 1:]

                continue

            if stripped.startswith("A:Prompt^") and path_stack:
                prompt_parts = stripped.split("^")
                translated_label = (
                    prompt_parts[1] if len(prompt_parts) > 1 else ""
                )
                translations[tuple(path_stack)] = translated_label

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
        sub_type_formatted = "".join((self.sub_type or "").split())

        if language in self.LANGUAGES:
            lang_code = self.LANGUAGES[language]["code"]
        else:
            lang_code = language.split("-")[0]

        return (
            f"{module_formatted}_{self.main_type}_{sub_type_formatted}-"
            f"{layer}-{lang_code}.trs"
        )


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

    test_translations = {"Test Field": "Testfält"}

    generator = TRSGenerator("ESSPRO", "Cust", "sv-SE")
    content = generator.generate_header() + generator.generate_content(
        test_data,
        test_translations,
    )
    print(content)
