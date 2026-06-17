"""
IFS Language Automation Logger
Logs all actions, decisions, and skip reasons
"""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


class IFSLogger:
    """Logger for IFS language automation tool"""
    
    def __init__(self, log_file: str = "Log.txt"):
        self.log_file = Path(log_file)
        self.entries = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}"
        self.entries.append(entry)
        print(entry)  # Also print to console
        
    def info(self, message: str):
        """Log info message"""
        self.log(message, "INFO")
        
    def warning(self, message: str):
        """Log warning message"""
        self.log(message, "WARN")
        
    def error(self, message: str):
        """Log error message"""
        self.log(message, "ERROR")
        
    def success(self, message: str):
        """Log success message"""
        self.log(message, "SUCCESS")
        
    def log_parsing_start(self, xml_file: str):
        """Log start of XML parsing"""
        self.info(f"Starting XML parsing: {xml_file}")
        
    def log_parsing_complete(self, stats: Dict[str, int]):
        """Log parsing completion with statistics"""
        self.info(f"XML parsing complete")
        self.info(f"  Logical Units: {stats['total_logical_units']}")
        self.info(f"  Views: {stats['total_views']}")
        self.info(f"  Total Columns: {stats['total_columns']}")
        self.info(f"  Custom Columns (C_*): {stats['custom_columns']}")
        self.info(f"  Standard Columns (skipped): {stats['standard_columns']}")
        
    def log_field_processed(self, field_name: str, label: str):
        """Log processing of a custom field"""
        self.info(f"Processing custom field: {field_name} -> '{label}'")
        
    def log_field_skipped(self, field_name: str, reason: str):
        """Log skipping of a field"""
        self.info(f"Skipping field: {field_name} (Reason: {reason})")
        
    def log_translation_start(self, language: str, field_count: int):
        """Log start of translation"""
        self.info(f"Starting translation to {language}: {field_count} fields")
        
    def log_translation_complete(self, language: str):
        """Log translation completion"""
        self.success(f"Translation to {language} complete")
        
    def log_file_generation(self, file_path: str, action: str):
        """Log file generation or update"""
        self.info(f"{action}: {file_path}")
        
    def log_validation_start(self, file_path: str):
        """Log start of validation"""
        self.info(f"Validating: {file_path}")
        
    def log_validation_success(self, file_path: str):
        """Log successful validation"""
        self.success(f"Validation passed: {file_path}")
        
    def log_validation_error(self, file_path: str, error: str):
        """Log validation error"""
        self.error(f"Validation failed for {file_path}: {error}")
        
    def write_to_file(self):
        """Write all log entries to file"""
        try:
            # Read existing content if file exists
            existing_content = ""
            if self.log_file.exists():
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            
            # Append new entries
            with open(self.log_file, 'w', encoding='utf-8') as f:
                if existing_content:
                    f.write(existing_content)
                    if not existing_content.endswith('\n'):
                        f.write('\n')
                    f.write('\n')  # Extra blank line
                
                f.write(f"=== Automation Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                for entry in self.entries:
                    f.write(entry + '\n')
                f.write('\n')
                
            self.success(f"Log written to {self.log_file}")
            
        except Exception as e:
            self.error(f"Failed to write log file: {e}")
            
    def get_summary(self) -> str:
        """Get a summary of the log"""
        info_count = sum(1 for e in self.entries if '[INFO]' in e)
        warn_count = sum(1 for e in self.entries if '[WARN]' in e)
        error_count = sum(1 for e in self.entries if '[ERROR]' in e)
        success_count = sum(1 for e in self.entries if '[SUCCESS]' in e)
        
        return f"Log Summary: {info_count} info, {warn_count} warnings, {error_count} errors, {success_count} success"
