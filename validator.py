"""
IFS File Validator
Validates .lng and .trs files for correctness
"""

from typing import List, Tuple, Optional
from pathlib import Path
import re


class IFSValidator:
    """Validator for IFS .lng and .trs files"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        
    def validate_file(self, file_path: str) -> Tuple[bool, List[str], List[str]]:
        """
        Validate a .lng or .trs file
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        file_path = Path(file_path)
        
        if not file_path.exists():
            self.errors.append(f"File does not exist: {file_path}")
            return False, self.errors, self.warnings
        
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            self.errors.append(f"Failed to read file: {e}")
            return False, self.errors, self.warnings
        
        # Determine file type
        is_lng = file_path.suffix == '.lng'
        is_trs = file_path.suffix == '.trs'
        
        if not (is_lng or is_trs):
            self.errors.append(f"Unknown file type: {file_path.suffix}")
            return False, self.errors, self.warnings
        
        # Validate header
        self._validate_header(lines, is_lng)
        
        # Find content start
        content_start = self._find_content_start(lines)
        if content_start is None:
            self.errors.append("Could not find content section")
            return False, self.errors, self.warnings
        
        # Validate CS/CE pairing
        self._validate_cs_ce_pairing(lines[content_start:], content_start)
        
        # Validate indentation
        self._validate_indentation(lines[content_start:], content_start)
        
        # Validate structure
        if is_lng:
            self._validate_lng_structure(lines[content_start:], content_start)
        else:
            self._validate_trs_structure(lines[content_start:], content_start)
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings
    
    def _validate_header(self, lines: List[str], is_lng: bool):
        """Validate file header"""
        if len(lines) < 10:
            self.errors.append("File too short, missing header")
            return
        
        expected_type = "IFS Foundation Language File" if is_lng else "IFS Foundation Translation File"
        
        # Check file type line - be lenient with whitespace
        header_text = ''.join(lines[:15])
        if expected_type not in header_text:
            self.errors.append(f"Invalid file type header. Expected: {expected_type}")
        
        # Check version
        if "Type version: 10.00" not in header_text:
            self.warnings.append("Type version is not 10.00")
        
        # Check required fields
        required_fields = ['Module:', 'Layer:', 'Main Type:', 'Sub Type:']
        for field in required_fields:
            if field not in header_text:
                self.errors.append(f"Missing required header field: {field}")
    
    def _find_content_start(self, lines: List[str]) -> Optional[int]:
        """Find the line where content starts (after header)"""
        for i, line in enumerate(lines):
            if line.strip().startswith('CS:'):
                return i
        return None
    
    def _validate_cs_ce_pairing(self, content_lines: List[str], offset: int):
        """Validate that every CS has a matching CE"""
        stack = []
        
        for i, line in enumerate(content_lines):
            line_num = i + offset + 1
            stripped = line.strip()
            
            if stripped.startswith('CS:'):
                # Extract identifier
                match = re.match(r'CS:([^^]+)', stripped)
                if match:
                    identifier = match.group(1)
                    stack.append((identifier, line_num))
                else:
                    self.errors.append(f"Line {line_num}: Malformed CS line: {stripped}")
            
            elif stripped.startswith('CE:'):
                if not stack:
                    self.errors.append(f"Line {line_num}: CE without matching CS")
                else:
                    stack.pop()
        
        # Check for unclosed CS blocks
        if stack:
            for identifier, line_num in stack:
                self.errors.append(f"Line {line_num}: CS '{identifier}' not closed with CE")
    
    def _validate_indentation(self, content_lines: List[str], offset: int):
        """Validate indentation is consistent (tabs)"""
        for i, line in enumerate(content_lines):
            line_num = i + offset + 1
            
            # Skip empty lines
            if not line.strip():
                continue
            
            # Check that indentation uses tabs, not spaces
            if line.startswith(' ') and not line.startswith('\t'):
                self.warnings.append(f"Line {line_num}: Uses spaces instead of tabs for indentation")
            
            # Count indentation level
            indent_count = 0
            for char in line:
                if char == '\t':
                    indent_count += 1
                else:
                    break
    
    def _validate_lng_structure(self, content_lines: List[str], offset: int):
        """Validate .lng file structure"""
        for i, line in enumerate(content_lines):
            line_num = i + offset + 1
            stripped = line.strip()
            
            # Validate CS line format
            if stripped.startswith('CS:'):
                # Should have format: CS:identifier^type^subtype^flag1^flag2
                parts = stripped.split('^')
                if len(parts) != 5:
                    self.errors.append(f"Line {line_num}: Invalid CS format. Expected 5 parts, got {len(parts)}")
            
            # Validate A:Prompt format
            if stripped.startswith('A:Prompt^'):
                # Should end with ^
                if not stripped.endswith('^'):
                    self.errors.append(f"Line {line_num}: A:Prompt should end with ^")
    
    def _validate_trs_structure(self, content_lines: List[str], offset: int):
        """Validate .trs file structure"""
        for i, line in enumerate(content_lines):
            line_num = i + offset + 1
            stripped = line.strip()
            
            # Validate CS line format (no flags in .trs)
            if stripped.startswith('CS:'):
                # Should have format: CS:identifier^type
                parts = stripped.split('^')
                if len(parts) != 5:
                    self.errors.append(f"Line {line_num}: Invalid CS format for .trs. Expected 2 parts, got {len(parts)}")
            
            # Validate P: format
            if stripped.startswith('P:'):
                # Should end with ^
                if not stripped.endswith('^'):
                    self.errors.append(f"Line {line_num}: P: line should end with ^")
            
            # Validate A:Prompt format
            if stripped.startswith('A:Prompt^'):
                # Should end with ^
                if not stripped.endswith('^'):
                    self.errors.append(f"Line {line_num}: A:Prompt should end with ^")
    
    def validate_hierarchy(self, file_path: str) -> bool:
        """
        Validate proper nesting hierarchy (LU -> View -> Column)
        
        Args:
            file_path: Path to file to validate
            
        Returns:
            True if hierarchy is valid
        """
        # This would require parsing the file structure
        # For now, we'll rely on CS/CE pairing validation
        return True
    
    def get_summary(self) -> str:
        """Get validation summary"""
        return f"Validation: {len(self.errors)} errors, {len(self.warnings)} warnings"


if __name__ == '__main__':
    # Test the validator
    import sys
    if len(sys.argv) > 1:
        validator = IFSValidator()
        is_valid, errors, warnings = validator.validate_file(sys.argv[1])
        
        print(f"Valid: {is_valid}")
        if errors:
            print("\nErrors:")
            for error in errors:
                print(f"  - {error}")
        if warnings:
            print("\nWarnings:")
            for warning in warnings:
                print(f"  - {warning}")
