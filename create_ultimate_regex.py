#!/usr/bin/env python3
"""
Create the ultimate regex patterns based on actual AI KRT results
"""

import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'krt_web.settings')
django.setup()

from web.models import KRTSession
import re
from collections import defaultdict

def analyze_ai_resources():
    """Analyze all AI-generated KRT resources to create better regex patterns"""
    
    all_resources = []
    sessions = KRTSession.objects.filter(mode='llm', status='completed', resources_found__gt=5)
    
    print(f"Analyzing {sessions.count()} AI sessions...")
    
    for session in sessions:
        if session.krt_data:
            for resource in session.krt_data:
                all_resources.append({
                    'type': resource.get('RESOURCE TYPE', ''),
                    'name': resource.get('RESOURCE NAME', ''),
                    'source': resource.get('SOURCE', ''),
                    'identifier': resource.get('IDENTIFIER', ''),
                })
    
    print(f"Total resources: {len(all_resources)}")
    
    # Group by type
    by_type = defaultdict(list)
    for resource in all_resources:
        by_type[resource['type']].append(resource)
    
    # Analyze antibodies specifically
    print("\n🔬 ANTIBODY ANALYSIS:")
    antibodies = by_type.get('Antibody', [])
    print(f"Total antibodies: {len(antibodies)}")
    
    antibody_patterns = []
    for ab in antibodies[:20]:  # Look at first 20
        name = ab['name']
        print(f"  {name}")
        antibody_patterns.append(name)
    
    print("\n💻 SOFTWARE ANALYSIS:")
    software = by_type.get('Software/code', [])
    print(f"Total software: {len(software)}")
    
    software_patterns = []
    for sw in software[:20]:
        name = sw['name']
        print(f"  {name}")
        software_patterns.append(name)
    
    print("\n🧪 CHEMICAL ANALYSIS:")
    chemicals = by_type.get('Chemical, peptide, or recombinant protein', [])
    print(f"Total chemicals: {len(chemicals)}")
    
    for chem in chemicals[:20]:
        name = chem['name']
        print(f"  {name}")
    
    print("\n📋 PROTOCOL ANALYSIS:")
    protocols = by_type.get('Protocol', [])
    print(f"Total protocols: {len(protocols)}")
    
    for prot in protocols[:10]:
        name = prot['name']
        print(f"  {name}")
    
    print("\n🦠 VIRAL VECTOR ANALYSIS:")
    vectors = by_type.get('Viral vector', [])
    print(f"Total viral vectors: {len(vectors)}")
    
    for vec in vectors[:10]:
        name = vec['name']
        print(f"  {name}")
    
    return by_type

def create_enhanced_patterns(resources_by_type):
    """Create enhanced regex patterns based on actual AI data"""
    
    print("\n🎯 CREATING ENHANCED PATTERNS:")
    
    # Antibody patterns based on real data
    antibodies = resources_by_type.get('Antibody', [])
    print(f"\nAntibody patterns from {len(antibodies)} examples:")
    
    # Extract common antibody patterns
    ab_formats = []
    for ab in antibodies:
        name = ab['name']
        if '[' in name and ']' in name:
            ab_formats.append("bracket_format")
        if '(' in name and ')' in name:
            ab_formats.append("paren_format")
        if name.startswith('Anti-'):
            ab_formats.append("anti_prefix")
        if 'antibody' in name.lower():
            ab_formats.append("antibody_suffix")
    
    print("Common antibody formats:")
    from collections import Counter
    for fmt, count in Counter(ab_formats).most_common():
        print(f"  {fmt}: {count} times")
    
    # Software patterns
    software = resources_by_type.get('Software/code', [])
    print(f"\nSoftware patterns from {len(software)} examples:")
    
    sw_names = [sw['name'] for sw in software]
    unique_software = list(set(sw_names))
    print("Unique software tools:")
    for i, sw in enumerate(sorted(unique_software)[:30]):
        print(f"  {sw}")
    
    # Create comprehensive pattern suggestions
    print("\n📝 PATTERN SUGGESTIONS:")
    
    # Ultimate antibody pattern
    antibody_pattern = r"""
    # Ultimate antibody pattern covering all formats found in AI data
    PATTERN_ANTIBODY_ULTIMATE = re.compile(r'''
        (?:
            (?:Anti-|anti-|α-)?               # Optional anti- prefix
            (?:[A-Z0-9-]+)\s+                 # Target protein
            (?:antibody|Antibody)\s+          # antibody keyword
            (?:\[([A-Z0-9]+(?:\([A-Z0-9]+\))?)\]|  # [clone] format
               \(([A-Z0-9]+)\))               # (clone) format
        |
            (?:[A-Z0-9-]+)\s+                 # Target protein
            (?:Antibody|antibody)\s+          # antibody keyword  
            (?:\[([A-Z0-9]+)\]|\(([A-Z0-9]+)\))  # clone info
        |
            (?:Cleaved\s+)?                   # Optional "Cleaved"
            (?:[A-Z0-9-]+)\s+                 # Target
            (?:\([A-Za-z0-9]+\))?\s*          # Optional info in parens
            (?:Antibody|antibody)             # antibody keyword
        )
    ''', re.IGNORECASE | re.VERBOSE)
    """
    
    print(antibody_pattern)
    
    return {
        'antibodies': len(antibodies),
        'software': len(software),
        'unique_software': unique_software
    }

if __name__ == "__main__":
    resources = analyze_ai_resources()
    patterns = create_enhanced_patterns(resources)