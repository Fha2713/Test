"""
IFS .lng File Generator

Generates language files with proper CS/CE block structure
"""

from typing import Dict, Any, List
from pathlib import Path


class LNGGenerator:
    """Generator for IFS .lng language files"""
    
    def __init__(self, module: str, layer: str, main_type: str = "LU", sub_type: str = "Logical Unit"):
        self.module = module
        self.layer = layer
        self.main_type = main_type
        self.sub_type = sub_type
    
    def generate_header(self) -> str:
        """Generate .lng file header"""
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
            "-------------------------------------------------------"
        ]
        return '\r\n'.join(header) + '\r\n'
    
    def generate_content(self, data: Dict[str, Any]) -> str:
        """
        Generate complete .lng file content
        
        Args:
            data: Parsed and filtered data structure
            
        Returns:
            Complete .lng file content as string
        """
        lines = []
        
        # Process each logical unit
        for lu_id, lu_data in data['logical_units'].items():
            lu_lines = self._generate_lu_block(lu_data, indent_level=0)
            lines.extend(lu_lines)
        
        return ''.join(lines)
    
    def _generate_lu_block(self, lu_data: Dict[str, Any], indent_level: int) -> List[str]:
        """Generate CS/CE block for a Logical Unit"""
        lines = []
        indent = '\t' * indent_level
        
        # CS line for LU
        lu_name = lu_data['name']
        lines.append(f"{indent}CS:{lu_name}^LU^Logical Unit^N^N\r\n")
        
        # A:Prompt for LU
        lu_label = lu_data['label']
        lines.append(f"{indent}\tA:Prompt^{lu_label}^\r\n")
        
        # Process views
        for view_id, view_data in lu_data['views'].items():
            view_lines = self._generate_view_block(view_data, indent_level + 1)
            lines.extend(view_lines)
        
        # CE line for LU
        lines.append(f"{indent}CE:\r\n")
        
        return lines
    
    def _generate_view_block(self, view_data: Dict[str, Any], indent_level: int) -> List[str]:
        """Generate CS/CE block for a View"""
        lines = []
        indent = '\t' * indent_level
        
        # CS line for View
        view_control = view_data['control']
        lines.append(f"{indent}CS:{view_control}^LU^View^N^N\r\n")
        
        # Process columns (only custom fields)
        for col_id, col_data in view_data['columns'].items():
            if col_data['is_custom']:
                col_lines = self._generate_column_block(col_data, indent_level + 1)
                lines.extend(col_lines)
        
        # CE line for View
        lines.append(f"{indent}CE:\r\n")
        
        return lines
    
    def _generate_column_block(self, col_data: Dict[str, Any], indent_level: int) -> List[str]:
        """Generate CS/CE block for a Column"""
        lines = []
        indent = '\t' * indent_level
        
        # CS line for Column
        col_control = col_data['control']
        lines.append(f"{indent}CS:{col_control}^LU^Column^N^N\r\n")
        
        # A:Prompt for Column
        col_label = col_data['label']
        lines.append(f"{indent}\tA:Prompt^{col_label}^\r\n")
        
        # CE line for Column
        lines.append(f"{indent}CE:\r\n")
        
        return lines
    
    def generate_file(self, data: Dict[str, Any], output_path: str) -> str:
        """
        Generate complete .lng file
        
        Args:
            data: Parsed and filtered data structure
            output_path: Path to write the file
            
        Returns:
            Path to generated file
        """
        header = self.generate_header()
        content = self.generate_content(data)
        full_content = header + content
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            f.write(full_content)
        
        return str(output_file)
    
    def merge_with_existing(self, new_data: Dict[str, Any], existing_file: str) -> Dict[str, Any]:
        """
        Merge new data with existing .lng file to avoid duplicates
        
        Args:
            new_data: New data to add
            existing_file: Path to existing .lng file
            
        Returns:
            Merged data structure
        """
        existing_path = Path(existing_file)
        
        if not existing_path.exists():
            return new_data
        
        existing_data = self._parse_existing_file(existing_path)
        
        if existing_data['module'].upper() != new_data['module'].upper():
            raise ValueError(
                f"Cannot merge different modules: {existing_data['module']} and {new_data['module']}"
            )
        
        if existing_data['layer'].lower() != new_data['layer'].lower():
            raise ValueError(
                f"Cannot merge different layers: {existing_data['layer']} and {new_data['layer']}"
            )
        
        for lu_id, new_lu_data in new_data['logical_units'].items():
            if lu_id not in existing_data['logical_units']:
                existing_data['logical_units'][lu_id] = new_lu_data
                continue
            
            existing_lu_data = existing_data['logical_units'][lu_id]
            
            for view_id, new_view_data in new_lu_data['views'].items():
                if view_id not in existing_lu_data['views']:
                    existing_lu_data['views'][view_id] = new_view_data
                    continue
                
                existing_view_data = existing_lu_data['views'][view_id]
                
                for col_id, new_col_data in new_view_data['columns'].items():
                    if col_id not in existing_view_data['columns']:
                        existing_view_data['columns'][col_id] = new_col_data
        
        return existing_data
    
    def _parse_existing_file(self, existing_file: Path) -> Dict[str, Any]:
        """Parse an existing .lng file into the internal data structure"""
        data = {
            'module': self.module,
            'layer': self.layer,
            'logical_units': {}
        }
        
        with open(existing_file, 'r', encoding='utf-8-sig') as f:
            lines = f.read().splitlines()
        
        current_lu_id = None
        current_view_id = None
        current_col_id = None
        
        for raw_line in lines:
            line = raw_line.strip()
            
            if line.startswith('Module:'):
                data['module'] = line.split(':', 1)[1].strip()
                continue
            
            if line.startswith('Layer:'):
                data['layer'] = line.split(':', 1)[1].strip()
                continue
            
            if line.startswith('CS:'):
                parts = line[3:].split('^')
                control = parts[0].strip()
                node_type = parts[2].strip() if len(parts) > 2 else ''
                
                if node_type == 'Logical Unit':
                    current_lu_id = control
                    current_view_id = None
                    current_col_id = None
                    data['logical_units'].setdefault(current_lu_id, {
                        'name': control,
                        'label': control,
                        'views': {}
                    })
                
                elif node_type == 'View' and current_lu_id:
                    current_view_id = control
                    current_col_id = None
                    data['logical_units'][current_lu_id]['views'].setdefault(current_view_id, {
                        'control': control,
                        'label': control,
                        'columns': {}
                    })
                
                elif node_type == 'Column' and current_lu_id and current_view_id:
                    current_col_id = control
                    data['logical_units'][current_lu_id]['views'][current_view_id]['columns'].setdefault(
                        current_col_id,
                        {
                            'control': control,
                            'label': control,
                            'is_custom': True
                        }
                    )
                
                continue
            
            if line.startswith('A:Prompt^'):
                parts = line.split('^')
                label = parts[1] if len(parts) > 1 else ''
                
                if current_lu_id and current_view_id and current_col_id:
                    data['logical_units'][current_lu_id]['views'][current_view_id]['columns'][current_col_id]['label'] = label
                elif current_lu_id and current_view_id is None:
                    data['logical_units'][current_lu_id]['label'] = label
        
        return data
    
    def get_file_name(self, module: str, layer: str) -> str:
        """
        Get standard file name for .lng file
        
        Args:
            module: Module name (e.g., ESSPRO)
            layer: Layer name (e.g., Cust)
            
        Returns:
            File name (e.g., Esspro_LU_LogicalUnit-Cust.lng)
        """
        # Capitalize first letter, rest lowercase for module
        module_formatted = module.capitalize()
        return f"{module_formatted}_LU_LogicalUnit-{layer}.lng"


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
    
    generator = LNGGenerator('ESSPRO', 'Cust')
    content = generator.generate_header() + generator.generate_content(test_data)
    print(content)
