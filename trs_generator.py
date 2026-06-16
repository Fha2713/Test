"""
IFS .trs Translation File Generator

Generates translation files with P: and A:Prompt entries
"""

from typing import Dict, Any, List, Tuple
from pathlib import Path


class TRSGenerator:
    """Generator for IFS .trs translation files"""
    
    # Language mappings
    LANGUAGES = {
        'sv-SE': {'code': 'sv', 'name': 'Swedish'},
        'nb-NO': {'code': 'no', 'name': 'Norwegian'}
    }
    
    def __init__(self, module: str, layer: str, language: str, main_type: str = "LU", sub_type: str = "Logical Unit"):
        self.module = module
        self.layer = layer
        self.language = language
        self.main_type = main_type
        self.sub_type = sub_type
        
        # Get language code (e.g., 'sv' from 'sv-SE')
        if language in self.LANGUAGES:
            self.lang_code = self.LANGUAGES[language]['code']
            self.culture = language
        else:
            # Assume format like 'sv-SE'
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
    
    def generate_content(self, data: Dict[str, Any], translations: Dict[str, str], existing_translations: Dict[Tuple[str, str, str], str] = None) -> str:
        """
        Generate complete .trs file content
        
        Args:
            data: Parsed and filtered data structure
            translations: Dictionary mapping English labels to translated labels
            existing_translations: Existing translations mapped by LU, View and Column
            
        Returns:
            Complete .trs file content as string
        """
        lines = []
        existing_translations = existing_translations or {}
        
        # Process each logical unit
        for lu_id, lu_data in data['logical_units'].items():
            lu_lines = self._generate_lu_block(lu_data, translations, existing_translations, indent_level=0)
            lines.extend(lu_lines)
        
        return ''.join(lines)
    
    def _generate_lu_block(self, lu_data: Dict[str, Any], translations: Dict[str, str], existing_translations: Dict[Tuple[str, str, str], str], indent_level: int) -> List[str]:
        """Generate CS/CE block for a Logical Unit"""
        lines = []
        indent = '\t' * indent_level
        
        # CS line for LU (no flags in .trs)
        lu_name = lu_data['name']
        lines.append(f"{indent}CS:{lu_name}^LU\r\n")
        
        # Process views
        for view_id, view_data in lu_data['views'].items():
            view_lines = self._generate_view_block(lu_name, view_data, translations, existing_translations, indent_level + 1)
            lines.extend(view_lines)
        
        # CE line for LU
        lines.append(f"{indent}CE:\r\n")
        
        return lines
    
    def _generate_view_block(self, lu_name: str, view_data: Dict[str, Any], translations: Dict[str, str], existing_translations: Dict[Tuple[str, str, str], str], indent_level: int) -> List[str]:
        """Generate CS/CE block for a View"""
        lines = []
        indent = '\t' * indent_level
        
        # CS line for View (no flags in .trs)
        view_control = view_data['control']
        lines.append(f"{indent}CS:{view_control}^LU\r\n")
        
        # Process columns (only custom fields)
        for col_id, col_data in view_data['columns'].items():
            if col_data['is_custom']:
                col_lines = self._generate_column_block(lu_name, view_control, col_data, translations, existing_translations, indent_level + 1)
                lines.extend(col_lines)
        
        # CE line for View
        lines.append(f"{indent}CE:\r\n")
        
        return lines
    
    def _generate_column_block(self, lu_name: str, view_control: str, col_data: Dict[str, Any], translations: Dict[str, str], existing_translations: Dict[Tuple[str, str, str], str], indent_level: int) -> List[str]:
        """Generate CS/CE block for a Column"""
        lines = []
        indent = '\t' * indent_level
        
        # CS line for Column (no flags in .trs)
        col_control = col_data['control']
        lines.append(f"{indent}CS:{col_control}^LU\r\n")
        
        # P: line for original English text
        original_label = col_data['label']
        lines.append(f"{indent}\tP:{original_label}^\r\n")
        
        # A:Prompt for translated text
        translation_key = (lu_name, view_control, col_control)
        translated_label = existing_translations.get(translation_key, translations.get(original_label, original_label))
        lines.append(f"{indent}\tA:Prompt^{translated_label}^\r\n")
        
        # CE line for Column
        lines.append(f"{indent}CE:\r\n")
        
        return lines
    
    def read_existing_translations(self, existing_file: str) -> Dict[Tuple[str, str, str], str]:
        """Read existing translations mapped by Logical Unit, View and Column"""
        existing_path = Path(existing_file)
        
        if not existing_path.exists():
            return {}
        
        translations = {}
        
        with open(existing_path, 'r', encoding='utf-8-sig') as f:
            lines = f.read().splitlines()
        
        current_lu = None
        current_view = None
        current_column = None
        
        for raw_line in lines:
            line = raw_line.strip()
            
            if line.startswith('CS:'):
                control = line[3:].split('^', 1)[0].strip()
                indent_level = len(raw_line) - len(raw_line.lstrip('\t'))
                
                if indent_level == 0:
                    current_lu = control
                    current_view = None
                    current_column = None
                elif indent_level == 1 and current_lu:
                    current_view = control
                    current_column = None
                elif indent_level == 2 and current_lu and current_view:
                    current_column = control
                
                continue
            
            if line.startswith('A:Prompt^') and current_lu and current_view and current_column:
                parts = line.split('^')
                translated_label = parts[1] if len(parts) > 1 else ''
                translations[(current_lu, current_view, current_column)] = translated_label
        
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
        existing_translations = self.read_existing_translations(output_path)
        header = self.generate_header()
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
            language: Language code (e.g., sv-SE)
            
        Returns:
            File name (e.g., Esspro_LU_LogicalUnit-Cust-sv.trs)
        """
        # Capitalize first letter, rest lowercase for module
        module_formatted = module.capitalize()
        
        # Get language code
        if language in self.LANGUAGES:
            lang_code = self.LANGUAGES[language]['code']
        else:
            lang_code = language.split('-')[0]
        
        return f"{module_formatted}_LU_LogicalUnit-{layer}-{lang_code}.trs"


if __name__ == '__main__':
    # Test the generator
    test_data = {
        'module': 'ESSPRO',
        'layer': 'Cust',
        'logical_units': {
            'TestLU': {
                'name': 'TestLU',
                'label': 'Test Logical Unit',
                'views': {
                    'TEST_VIEW': {
                        'control': 'TEST_VIEW',
                        'label': 'Test View',
                        'columns': {
                            'C_TEST_FIELD': {
                                'control': 'C_TEST_FIELD',
                                'label': 'Test Field',
                                'is_custom': True
                            }
                        }
                    }
                }
            }
        }
    }
    
    test_translations = {
        'Test Field': 'Testfält'
    }
    
    generator = TRSGenerator('ESSPRO', 'Cust', 'sv-SE')
    content = generator.generate_header() + generator.generate_content(test_data, test_translations)
    print(content)
