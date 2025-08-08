"""
KRT Validation - Validation functions for Key Resources Tables following ASAP guidelines
"""

from typing import List, Dict, Tuple, Optional


def validate_krt_completeness(krt_data: List[Dict[str, str]]) -> List[str]:
    """
    Validate KRT data according to ASAP Open Science guidelines.
    
    Args:
        krt_data: List of KRT entries
        
    Returns:
        List of validation warnings/recommendations
    """
    warnings = []
    
    if not krt_data:
        warnings.append("No KRT entries found. Please ensure all resources are properly extracted.")
        return warnings
    
    # Check for required fields in each entry
    required_fields = ['RESOURCE TYPE', 'RESOURCE NAME', 'IDENTIFIER', 'NEW/REUSE']
    
    for i, entry in enumerate(krt_data, 1):
        for field in required_fields:
            value = entry.get(field, '').strip()
            if not value or value.lower() in ['n/a', 'na', 'unknown', 'none', '']:
                warnings.append(f"Row {i}: Missing required field '{field}'")
    
    # Check for new dataset requirement
    has_new_dataset = any(
        entry.get('RESOURCE TYPE', '').lower() == 'dataset' and 
        entry.get('NEW/REUSE', '').lower() == 'new'
        for entry in krt_data
    )
    
    if not has_new_dataset:
        warnings.append(
            "This KRT does not include any new data. If you did collect data, add a row for the data you collected. "
            "If you did not collect data, add the text \"No new primary data were collected in this study\" "
            "to your Data/Code Availability Statement."
        )
    
    # Check for new software/code requirement
    has_new_code = any(
        entry.get('RESOURCE TYPE', '').lower() == 'software/code' and 
        entry.get('NEW/REUSE', '').lower() == 'new'
        for entry in krt_data
    )
    
    if not has_new_code:
        warnings.append(
            "This KRT does not include any new code. If you did generate code for this study, add a row outlining "
            "the code you generated. If you did not generate any code, add the text \"No code was generated for this study; "
            "all data cleaning, preprocessing, analysis, and visualization was performed using [insert program name(s)]\" "
            "to your Data/Code Availability Statement."
        )
    
    # Check for valid resource types
    valid_resource_types = {
        'dataset', 'software/code', 'protocol', 'antibody', 'bacterial strain',
        'viral vector', 'biological sample', 'chemical, peptide, or recombinant protein',
        'critical commercial assay', 'experimental model: cell line',
        'experimental model: organism/strain', 'oligonucleotide', 'recombinant dna', 'other'
    }
    
    for i, entry in enumerate(krt_data, 1):
        resource_type = entry.get('RESOURCE TYPE', '').lower().strip()
        if resource_type and resource_type not in valid_resource_types:
            warnings.append(f"Row {i}: Invalid resource type '{entry.get('RESOURCE TYPE')}'. Must be one of the predefined types.")
    
    # Check for proper identifier formats
    for i, entry in enumerate(krt_data, 1):
        identifier = entry.get('IDENTIFIER', '').strip()
        resource_type = entry.get('RESOURCE TYPE', '').lower()
        
        if identifier and identifier.lower() not in ['no identifier exists']:
            # Check for specific identifier requirements
            if resource_type == 'antibody' and 'rrid:' not in identifier.lower():
                warnings.append(f"Row {i}: Antibody should include RRID identifier when available")
            
            if resource_type == 'software/code' and not any(x in identifier.lower() for x in ['rrid:', 'doi:', 'http', 'github']):
                warnings.append(f"Row {i}: Software should include RRID, DOI, or URL identifier when available")
    
    # Check for missing version numbers in software
    for i, entry in enumerate(krt_data, 1):
        resource_type = entry.get('RESOURCE TYPE', '').lower()
        resource_name = entry.get('RESOURCE NAME', '')
        
        if resource_type == 'software/code' and resource_name:
            # Check if version number is included
            if not any(x in resource_name.lower() for x in ['version', 'v.', 'v ', ' v']):
                warnings.append(f"Row {i}: Software '{resource_name}' should include version number")
    
    return warnings


def get_krt_quality_score(krt_data: List[Dict[str, str]]) -> Tuple[int, int, List[str]]:
    """
    Calculate a quality score for the KRT data.
    
    Args:
        krt_data: List of KRT entries
        
    Returns:
        Tuple of (score, max_score, quality_notes)
    """
    if not krt_data:
        return 0, 100, ["No KRT data to evaluate"]
    
    score = 0
    max_score = 0
    quality_notes = []
    
    # Points for completeness (40 points max)
    max_score += 40
    required_fields = ['RESOURCE TYPE', 'RESOURCE NAME', 'IDENTIFIER', 'NEW/REUSE']
    complete_entries = 0
    
    for entry in krt_data:
        is_complete = True
        for field in required_fields:
            value = entry.get(field, '').strip()
            if not value or value.lower() in ['n/a', 'na', 'unknown', 'none', '']:
                is_complete = False
                break
        if is_complete:
            complete_entries += 1
    
    if krt_data:
        completeness_score = int((complete_entries / len(krt_data)) * 40)
        score += completeness_score
        quality_notes.append(f"Completeness: {complete_entries}/{len(krt_data)} entries complete ({completeness_score}/40 points)")
    
    # Points for identifier quality (30 points max)
    max_score += 30
    good_identifiers = 0
    
    for entry in krt_data:
        identifier = entry.get('IDENTIFIER', '').strip()
        if identifier and identifier != 'No identifier exists':
            # Check for high-quality identifiers
            if any(x in identifier.lower() for x in ['rrid:', 'doi:', 'geo:', 'cat#', 'catalog']):
                good_identifiers += 1
    
    if krt_data:
        identifier_score = int((good_identifiers / len(krt_data)) * 30)
        score += identifier_score
        quality_notes.append(f"Identifier quality: {good_identifiers}/{len(krt_data)} entries with structured IDs ({identifier_score}/30 points)")
    
    # Points for following guidelines (30 points max)
    max_score += 30
    guideline_score = 30
    
    # Check for new dataset
    has_new_dataset = any(
        entry.get('RESOURCE TYPE', '').lower() == 'dataset' and 
        entry.get('NEW/REUSE', '').lower() == 'new'
        for entry in krt_data
    )
    if not has_new_dataset:
        guideline_score -= 10
        quality_notes.append("Missing new dataset (-10 points)")
    
    # Check for new code
    has_new_code = any(
        entry.get('RESOURCE TYPE', '').lower() == 'software/code' and 
        entry.get('NEW/REUSE', '').lower() == 'new'
        for entry in krt_data
    )
    if not has_new_code:
        guideline_score -= 10
        quality_notes.append("Missing new software/code (-10 points)")
    
    # Check for version numbers in software
    software_entries = [e for e in krt_data if e.get('RESOURCE TYPE', '').lower() == 'software/code']
    if software_entries:
        versioned_software = sum(1 for e in software_entries 
                               if any(x in e.get('RESOURCE NAME', '').lower() 
                                     for x in ['version', 'v.', 'v ', ' v']))
        if versioned_software < len(software_entries):
            guideline_score -= 5
            quality_notes.append("Some software entries missing version numbers (-5 points)")
    
    score += max(0, guideline_score)
    quality_notes.append(f"Guideline adherence: {guideline_score}/30 points")
    
    return score, max_score, quality_notes


def suggest_krt_improvements(krt_data: List[Dict[str, str]]) -> List[str]:
    """
    Suggest specific improvements for KRT data.
    
    Args:
        krt_data: List of KRT entries
        
    Returns:
        List of improvement suggestions
    """
    suggestions = []
    
    if not krt_data:
        suggestions.append("Extract resources from the Methods section of your manuscript")
        return suggestions
    
    # Suggest specific identifier improvements
    for i, entry in enumerate(krt_data, 1):
        resource_type = entry.get('RESOURCE TYPE', '').lower()
        resource_name = entry.get('RESOURCE NAME', '')
        identifier = entry.get('IDENTIFIER', '')
        
        if resource_type == 'antibody' and identifier == 'No identifier exists':
            suggestions.append(f"Row {i}: Search antibodyregistry.org for RRID for '{resource_name}'")
        
        if resource_type == 'software/code' and identifier == 'No identifier exists':
            suggestions.append(f"Row {i}: Add official website URL or RRID for '{resource_name}'")
        
        if resource_type in ['experimental model: cell line'] and identifier == 'No identifier exists':
            suggestions.append(f"Row {i}: Search cellosaurus.org for RRID for '{resource_name}'")
    
    # Suggest adding missing resource types
    resource_types_found = {entry.get('RESOURCE TYPE', '').lower() for entry in krt_data}
    
    if 'protocol' not in resource_types_found:
        suggestions.append("Consider adding protocols used in your study (e.g., immunohistochemistry, PCR)")
    
    if 'dataset' not in resource_types_found:
        suggestions.append("Add datasets generated or used in your study")
    
    if 'software/code' not in resource_types_found:
        suggestions.append("Add software used for analysis (e.g., ImageJ, R, Python scripts)")
    
    return suggestions