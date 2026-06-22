"""
IFS .trs Translation File Generator
Generates translation files with P: and A:Prompt entries
"""

from typing import Dict, Any, List
from pathlib import Path

TranslationPath = tuple[str, ...]

class TRSGenerator:
    """Generator for IFS .trs translation files"""
    """standardmäßige Sprache auf Deutsch umgebaut von Mario (sv-SE auf de-DE)"""
    
    # Language mappings
    LANGUAGES = {
        'de-DE': {'code': 'de', 'name': 'German'}
    }
    
    def __init__(self, module: str, layer: str, language: str, main_type: str, sub_type: str):
        self.module = module
        self.layer = layer
        self.language = language
        self.main_type = main_type
        self.sub_type = sub_type
        
        # Get language code (e.g., 'de' from 'de-DE')
        if language in self.LANGUAGES:
            self.lang_code = self.LANGUAGES[language]['code']
            self.culture = language
        else:
            # Assume format like 'de-DE'
            self.lang_code = language.split('-')[0]
            self.culture = language
    
    def generate_header(self) -> str:
        """Generate .trs file header"""
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
            "-------------------------------------------------------"
        ]
        return '\r\n'.join(header) + '\r\n'
    

    """existing_translations: Dict[tuple[str. str. str], str] = None als Übergabeparameter wurde von Mario hinzugefügt"""
    def generate_content(self, data: Dict[str, Any], translations: Dict[str, str], existing_translations: Dict[TranslationPath, str] = None) -> str:
        """
        Generate complete .trs file content
        
        Args:
            data: Parsed and filtered data structure
            translations: Dictionary mapping English labels to translated labels
            existing_translations: Existing translations mapped by LU. View and Column
            
        Returns:
            Complete .trs file content as string
        """
        lines: List[str] = []
        existing_translations = existing_translations or {}

        for resource_data in data.get("translatable_resources").values():
            lines.extend(self._generate_translatable_resource_block(resource_data, translations, existing_translations, indent_level=0, path_stack=[]))

        return "".join(lines)
    
    def _generate_translatable_resource_block(self, resource_data: Dict[str, Any], translations: Dict[str, str], existing_translations: Dict[TranslationPath, str], indent_level: int, path_stack = List[str]) -> List[str]:
        """Generate CS/CE block for a Logical Unit"""
        lines: List[str] = []
        indent = '\t' * indent_level
        
        # CS line for LU (no flags in .trs)
        resource_name = resource_data.get("name") or resource_data.get("id")
        resource_type = resource_data.get("type") or self.sub_type
        lines.append(f"{indent}CS:{resource_name}^{self.main_type}^{resource_type}^N^N\r\n")

        current_path = tuple(path_stack + [resource_name])

        resource_label = resource_data.get("label", "")
        print(translations)
        
        """Änderungen Zuhause"""
        translated_label = translations.get(resource_label, resource_label)
        print(translated_label)

        if not translated_label:
            translated_label = translations.get(resource_label, resource_label)

        if resource_label:
            lines.append(f"{indent}\tP:{resource_label}^\r\n")
                    
        if translated_label:
            lines.append(f"{indent}\tA:{resource_name}^{translated_label}^\r\n")

        for nested_resource_data in resource_data.get("nested_resources").values():
            lines.extend(
                self._generate_nested_resource_block(
                    nested_resource_data,
                    translations,
                    existing_translations,
                    indent_level + 1,
                    list(current_path)
                )
            )
        
        # CE line for LU
        lines.append(f"{indent}CE:\r\n")
        
        return lines
    
    def _generate_nested_resource_block(self, resource_data: Dict[str, Any], translations: Dict[str, str], existing_translations: Dict[TranslationPath, str], indent_level: int, path_stack: List[str]) -> List[str]:
        """Generate CS/CE block for a View"""
        lines: List[str] = []
        indent = '\t' * indent_level
        
        # CS line for View (no flags in .trs)
        resource_control = resource_data.get("control") or resource_data.get("name") or resource_data.get("id")
        resource_type = resource_data.get("subtype") or resource_data.get("type") or "Resource"
        lines.append(f"{indent}CS:{resource_control}^{self.main_type}^{resource_type}^N^N\r\n")

        current_path = tuple(path_stack + [resource_control])
        resource_label = resource_data.get("label", "")
        translated_label = translations.get(resource_label, resource_label)

        if not translated_label:
            translated_label = translations.get(resource_label, resource_label)

        if resource_label:
            lines.append(f"{indent}\tP:{resource_label}^\r\n")

        if translated_label:
            lines.append(f"{indent}\tA:{resource_control}^{translated_label}^\r\n")

        nested_resources = resource_data.get("nested_resources")
        for nested_resource_data in nested_resources.values():
            lines.extend(
                self._generate_nested_resource_block(
                    nested_resource_data,
                    translations,
                    existing_translations,
                    indent_level + 1,
                    list(current_path)
                )
            )

        
        # CE line for View
        lines.append(f"{indent}CE:\r\n")
        
        return lines
    
    
    """"read_existing_translations Methode wurde von Mario erstellt"""
    def read_existing_translations(self, existing_file: str) -> Dict[tuple[str, str, str], str]:
        existing_path = Path(existing_file)

        if not existing_path.exists():
            return {}

        translations: Dict[TranslationPath, str] = {}

        with open(existing_path, 'r', encoding='utf-8-sig') as f:
            lines = f.read().splitlines()

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

            if stripped.startswith("A:") and path_stack:
                a_parts = stripped[2:].split("^")

                control = a_parts[0].strip() if len(a_parts) > 0 else ""
                translated_label = a_parts[1].strip() if len(a_parts) > 1 else ""

                if control and translated_label:
                    translations[tuple(path_stack)] = translated_label

            return translations
        
    def generate_file(self, data: Dict[str, Any], translations: Dict[str, str], output_path: str) -> str:
        """
        Generate complete .trs file
        
        Args:
            data: Parsed and filtered data structure
            translations: Dictionary mapping English labels to translated labels
            output_path: Path to write the file
            
        Returns:
            Path to generated file
        """

        """"existing_translations als Variable wurde von Mario hinzugefügt"""
        existing_translations = self.read_existing_translations(output_path)
        header = self.generate_header()

        """"existing_translations als Parameter wurde von Mario beigefügt"""
        content = self.generate_content(data, translations, existing_translations)
        
        full_content = header + content
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            f.write(full_content)
        
        return str(output_file)
    
    def get_file_name(self, module: str, layer: str, language: str) -> str:
        """
        Get standard file name for .trs file
        
        Args:
            module: Module name (e.g., ESSPRO)
            layer: Layer name (e.g., Cust)
            language: Language code (e.g., de-DE)
            
        Returns:
            File name (e.g., Esspro_LU_LogicalUnit-Cust-de.trs)
        """
        # Capitalize first letter, rest lowercase for module
        module_formatted = module.capitalize()
        sub_type_formatted = "".join((self.sub_type or "").split())
        
        # Get language code
        if language in self.LANGUAGES:
            lang_code = self.LANGUAGES[language]['code']
        else:
            lang_code = language.split('-')[0]
        
        return f"{module_formatted}_{self.main_type}_{sub_type_formatted}-{layer}-{lang_code}.trs"


# if __name__ == '__main__':
#     # Test the generator
#     test_data = {
#         'module': 'ESSPRO',
#         'layer': 'Cust',
#         'logical_units': {
#             'TestLU': {
#                 'name': 'TestLU',
#                 'label': 'Test Logical Unit',
#                 'subcontents': {
#                     'TEST_VIEW': {
#                         'control': 'TEST_VIEW',
#                         'label': 'Test View',
#                         'columns': {
#                             'C_TEST_FIELD': {
#                                 'control': 'C_TEST_FIELD',
#                                 'label': 'Test Field',
#                                 'is_custom': True
#                             }
#                         }
#                     }
#                 }
#             }
#         }
#     }
    
#     test_translations = {
#         'Test Field': 'Testfält'
#     }
    
#     generator = TRSGenerator('ESSPRO', 'Cust', 'de-DE')
#     content = generator.generate_header() + generator.generate_content(test_data, test_translations)
#     print(content)
