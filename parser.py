"""
IFS TranslatableResources XML Parser
Extracts custom fields (C_* and DM_* prefix) from XML files
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, List
from pathlib import Path


class IFSXMLParser:
    """Parser for IFS TranslatableResources XML files"""
    """DM_-Präfix von Mario hinzugefügt"""
    
    NAMESPACE = {'ifs': 'types.scan.translation.fnd.ifsworld.com'}
    
    def __init__(self, xml_path: str):
        self.xml_path = Path(xml_path)
        self.tree = None
        self.root = None
        
    def parse(self) -> Dict[str, Any]:
        """
        Parse XML file and extract structure
        
        Returns:
            Dictionary containing module, layer, and logical unit hierarchy
        """
        self.tree = ET.parse(self.xml_path)
        self.root = self.tree.getroot()
        
        # Extract root attributes
        result = {
            'type': self.root.get('type'),
            'module': self.root.get('module'),
            'version': self.root.get('version'),
            'layer': self.root.get('layer'),
            'sub_type': None,
            'translatable_resources': {}
        }
        
        # Process each TranslatableResource (Logical Unit)
        # Use .// to search recursively and handle any namespace
        for resource_elem in self.root:
            if 'TranslatableResource' in resource_elem.tag:
                resource_data = self._parse_translatable_resource(resource_elem)
                if resource_data:
                    resource_id = resource_elem.get('ID')
                    if not result.get('sub_type'):
                        result['sub_type'] = resource_elem.get('type')
                    result['translatable_resources'][resource_id] = resource_data
        
        return result
    
    """label braucht es auch nicht unbedingt"""
    def _parse_translatable_resource(self, resource_elem: ET.Element) -> Dict[str, Any]:
        """Parse a top-level TranslatableResource element"""
        resource_data = {
            'id': resource_elem.get('ID'),
            'name': resource_elem.get('name') or resource_elem.get('ID'),
            'type': resource_elem.get('type'),
            'label': self._get_text(resource_elem),
            'is_custom': resource_elem.get('ID').split(".")[-1].startswith(('C', 'Dm')),
            'nested_resources': {}
        }

        # print(resource_data)
        
        for child in resource_elem:
            if 'Resource' in child.tag:
                nested_resource_data = self._parse_nested_resource(child)
                if nested_resource_data:
                    nested_resource_id = child.get('control') or child.get('ID')
                    resource_data['nested_resources'][nested_resource_id] = nested_resource_data
        
        # print(resource_data)
        return resource_data

    
    """label muss nicht immer dabei sein"""
    def _parse_nested_resource(self, resource_elem: ET.Element) -> Dict[str, Any]:
        """Parse a nested Resource element recursively"""
        resource_control = resource_elem.get('control') or resource_elem.get('ID')
        resource_data = {
            'id': resource_elem.get('ID'),
            'control': resource_control,
            'subtype': resource_elem.get('subtype'),
            'label': self._get_text(resource_elem),
            'is_custom': resource_control.split(".")[-1].startswith(('C', 'Dm')) if resource_control else False,
            'nested_resources': {}
        }
        
        for child in resource_elem:
            if 'Resource' in child.tag:
                nested_resource_data = self._parse_nested_resource(child)
                if nested_resource_data:
                    nested_resource_id = child.get('control') or child.get('ID')
                    resource_data['nested_resources'][nested_resource_id] = nested_resource_data
        
        # print(resource_data)
        return resource_data
    
    """Text ist nicht immer CDATA"""
    def _get_text(self, elem: ET.Element) -> str:
        """Extract text from CDATA section"""
        # Find Text element - iterate through children
        for child in elem:
            if 'Text' in child.tag:
                if child.text:
                    return child.text.strip()
        return ''
    
    """Custom Fields achtet nur noch auf 'Logical Unit' ID nicht mehr auf 'Control' """ 
    def extract_custom_fields(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter to only include custom fields (C_* prefix)
        
        Args:
            parsed_data: Full parsed data structure
            
        Returns:
            Filtered data containing only custom fields
        """
        result = {
            'type': parsed_data['type'],
            'module': parsed_data['module'],
            'version': parsed_data['version'],
            'layer': parsed_data['layer'],
            'sub_type': parsed_data.get('sub_type'),
            'translatable_resources': {}
        }
        
        for resource_id, resource_data in parsed_data['translatable_resources'].items():
            filtered_resource = {
                'id': resource_data['id'],
                'name': resource_data['name'],
                'type': resource_data['type'],
                'label': resource_data['label'],
                'nested_resources': {}
            }
            
            for nested_resource_id, nested_resource_data in resource_data['nested_resources'].items():
                filtered_nested_resource = self._filter_custom_resources(nested_resource_data)
                if filtered_nested_resource:
                    filtered_resource['nested_resources'][nested_resource_id] = filtered_nested_resource
            
            if filtered_resource['nested_resources']:
                result['translatable_resources'][resource_id] = filtered_resource
        
        # print(result)
        return result

    
    def _filter_custom_resources(self, resource_data: Dict[str, Any], keep_full_branch: bool = False) -> Dict[str, Any]:
        """Return resource with only custom nested resources, or None if empty"""

        is_custom =  resource_data.get('is_custom', False)
        keep_current_branch = keep_full_branch or is_custom

        filtered_resource = {
            'id': resource_data.get('id'),
            'control': resource_data.get('control'),
            'subtype': resource_data.get('subtype'),
            'label': resource_data.get('label', ''),
            'is_custom': is_custom,
            'nested_resources': {}
        }

        for nested_resource_id, nested_resource_data in resource_data.get('nested_resources', {}).items():
            if keep_current_branch:
                filtered_resource['nested_resources'][nested_resource_id] = nested_resource_data
            else: 
                filtered_nested_resource = self._filter_custom_resources(nested_resource_data, keep_full_branch = False)
                if filtered_nested_resource: 
                    filtered_resource['nested_resources'][nested_resource_id] = filtered_nested_resource
 
        if keep_current_branch or filtered_resource['nested_resources']:
            return filtered_resource

        return None
    
    def get_statistics(self, parsed_data: Dict[str, Any]) -> Dict[str, int]:
        """Get statistics about parsed data"""
        stats = {
            'total_translatable_resources': 0,
            'total_nested_resources': 0,
            'custom_resources': 0,
            'standard_resources': 0
        }
        
        for resource_data in parsed_data['translatable_resources'].values():
            stats['total_translatable_resources'] += 1
            self._count_nested_resources(resource_data, stats)
        
        return stats
    
    def _count_nested_resources(self, resource_data: Dict[str, Any], stats: Dict[str, int]):
        """Count nested resources recursively"""
        for nested_resource_data in resource_data.get('nested_resources', {}).values():
            stats['total_nested_resources'] += 1
            if nested_resource_data.get('is_custom'):
                stats['custom_resources'] += 1
            else:
                stats['standard_resources'] += 1
            self._count_nested_resources(nested_resource_data, stats)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        parser = IFSXMLParser(sys.argv[1])
        data = parser.parse()
        custom_data = parser.extract_custom_fields(data)
        stats = parser.get_statistics(data)
        
        print(f"Module: {data['module']}")
        print(f"Layer: {data['layer']}")
        print(f"Statistics: {stats}")
        print(f"\nCustom resources found: {stats['custom_resources']}")
