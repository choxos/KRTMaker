"""
Statistics views for KRT Maker - Research Resource Analytics
Provides comprehensive analysis of resource usage patterns, trends, and policy insights
"""

from django.views.generic import TemplateView
from django.db.models import Count, Avg, Sum, Q, F
from django.db.models.functions import TruncMonth, TruncYear
from django.utils import timezone
from datetime import datetime, timedelta
import json
from collections import defaultdict, Counter

from .models import KRTSession, Article, XMLFile, SystemMetrics


class StatisticsView(TemplateView):
    """Comprehensive statistics page for research resource analysis"""
    template_name = 'web/statistics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Basic metrics
        context.update(self._get_basic_metrics())
        
        # Resource analysis
        context.update(self._get_resource_analysis())
        
        # Temporal trends
        context.update(self._get_temporal_trends())
        
        # Research field analysis
        context.update(self._get_research_field_analysis())
        
        # Policy insights
        context.update(self._get_policy_insights())
        
        # Quality and reproducibility metrics
        context.update(self._get_quality_metrics())
        
        return context
    
    def _get_basic_metrics(self):
        """Get basic system metrics"""
        completed_sessions = KRTSession.objects.filter(status='completed')
        total_articles = Article.objects.count()
        
        return {
            'total_sessions': KRTSession.objects.count(),
            'completed_sessions': completed_sessions.count(),
            'total_articles': total_articles,
            'total_resources_extracted': sum(s.resources_found for s in completed_sessions),
            'avg_resources_per_paper': completed_sessions.aggregate(Avg('resources_found'))['resources_found__avg'] or 0,
            'avg_processing_time': completed_sessions.aggregate(Avg('processing_time'))['processing_time__avg'] or 0,
            'bioRxiv_papers': completed_sessions.filter(input_method='url').count(),
            'uploaded_papers': completed_sessions.filter(input_method='upload').count(),
        }
    
    def _get_resource_analysis(self):
        """Analyze resource types, sources, and new/reuse patterns"""
        completed_sessions = KRTSession.objects.filter(status='completed', krt_data__isnull=False)
        
        resource_types = defaultdict(int)
        sources = defaultdict(int)
        new_reuse = {'new': 0, 'reuse': 0, 'unknown': 0}
        vendor_analysis = defaultdict(int)
        software_analysis = defaultdict(int)
        identifier_types = defaultdict(int)
        
        # Commercial vs academic sources
        commercial_vendors = {
            'sigma aldrich', 'sigma-aldrich', 'abcam', 'biolegend', 'thermofisher',
            'thermo scientific', 'life technologies', 'invitrogen', 'gibco',
            'millipore', 'merck', 'bd biosciences', 'r&d systems', 'cell signaling',
            'santa cruz', 'novus biologicals', 'avanti polar lipids', 'cayman chemical'
        }
        
        academic_sources = {
            'this study', 'addgene', 'atcc', 'protein data bank', 'ncbi', 'uniprot',
            'jackson laboratory', 'ensembl', 'genbank', 'european bioinformatics institute'
        }
        
        commercial_count = 0
        academic_count = 0
        other_sources_count = 0
        
        for session in completed_sessions:
            if session.krt_data:
                for resource in session.krt_data:
                    # Resource type analysis
                    res_type = resource.get('RESOURCE TYPE', 'Unknown')
                    resource_types[res_type] += 1
                    
                    # Source analysis
                    source = resource.get('SOURCE', 'Unknown').lower()
                    sources[source] += 1
                    
                    # Categorize source type
                    if any(vendor in source for vendor in commercial_vendors):
                        commercial_count += 1
                        vendor_analysis[source] += 1
                    elif any(acad in source for acad in academic_sources):
                        academic_count += 1
                    else:
                        other_sources_count += 1
                    
                    # New/Reuse analysis
                    new_reuse_val = resource.get('NEW/REUSE', '').lower()
                    if new_reuse_val == 'new':
                        new_reuse['new'] += 1
                    elif new_reuse_val == 'reuse':
                        new_reuse['reuse'] += 1
                    else:
                        new_reuse['unknown'] += 1
                    
                    # Software analysis
                    if res_type.lower() in ['software/code', 'software']:
                        software_name = resource.get('RESOURCE NAME', '').lower()
                        software_analysis[software_name] += 1
                    
                    # Identifier analysis
                    identifier = resource.get('IDENTIFIER', '')
                    if 'rrid:' in identifier.lower():
                        identifier_types['RRID'] += 1
                    elif 'doi:' in identifier.lower() or identifier.startswith('10.'):
                        identifier_types['DOI'] += 1
                    elif 'addgene' in identifier.lower():
                        identifier_types['Addgene'] += 1
                    elif 'catalog' in identifier.lower() or 'cat' in identifier.lower():
                        identifier_types['Catalog Number'] += 1
                    elif identifier.lower() in ['no identifier exists', 'n/a', '']:
                        identifier_types['No Identifier'] += 1
                    else:
                        identifier_types['Other'] += 1
        
        return {
            'resource_types': dict(sorted(resource_types.items(), key=lambda x: x[1], reverse=True)),
            'top_sources': dict(sorted(sources.items(), key=lambda x: x[1], reverse=True)[:20]),
            'new_reuse_distribution': new_reuse,
            'commercial_vs_academic': {
                'commercial': commercial_count,
                'academic': academic_count,
                'other': other_sources_count
            },
            'top_vendors': dict(sorted(vendor_analysis.items(), key=lambda x: x[1], reverse=True)[:10]),
            'top_software': dict(sorted(software_analysis.items(), key=lambda x: x[1], reverse=True)[:10]),
            'identifier_types': dict(sorted(identifier_types.items(), key=lambda x: x[1], reverse=True)),
            'total_resources': sum(resource_types.values())
        }
    
    def _get_temporal_trends(self):
        """Analyze trends over time"""
        # Monthly trends
        monthly_data = (KRTSession.objects
                       .filter(status='completed')
                       .annotate(month=TruncMonth('created_at'))
                       .values('month')
                       .annotate(
                           count=Count('id'),
                           total_resources=Sum('resources_found'),
                           avg_resources=Avg('resources_found')
                       )
                       .order_by('month'))
        
        # Method usage trends
        method_trends = (KRTSession.objects
                        .filter(status='completed')
                        .annotate(month=TruncMonth('created_at'))
                        .values('month', 'mode')
                        .annotate(count=Count('id'))
                        .order_by('month', 'mode'))
        
        return {
            'monthly_trends': list(monthly_data),
            'method_trends': list(method_trends)
        }
    
    def _get_research_field_analysis(self):
        """Analyze by research fields based on keywords and categories"""
        completed_sessions = KRTSession.objects.filter(
            status='completed', 
            keywords__isnull=False
        ).exclude(keywords='')
        
        field_keywords = defaultdict(int)
        field_resources = defaultdict(list)
        
        # Define research field mapping
        field_mapping = {
            'immunology': ['immun', 'antibody', 'antigen', 'cytokine', 'lymphocyte', 'macrophage'],
            'genetics': ['gene', 'dna', 'rna', 'crispr', 'pcr', 'sequencing', 'genome'],
            'cell_biology': ['cell', 'protein', 'enzyme', 'mitochondr', 'nucleus', 'membrane'],
            'neuroscience': ['neuro', 'brain', 'synapse', 'neuron', 'cognitive'],
            'cancer': ['cancer', 'tumor', 'oncolog', 'metasta', 'chemotherapy'],
            'microbiology': ['bacteria', 'virus', 'microb', 'pathogen', 'infection'],
            'biochemistry': ['biochem', 'metabol', 'enzyme', 'catalyst', 'reaction'],
            'developmental': ['develop', 'embryo', 'stem cell', 'differentiat']
        }
        
        for session in completed_sessions:
            if session.keywords:
                try:
                    keywords = json.loads(session.keywords) if isinstance(session.keywords, str) else session.keywords
                    if isinstance(keywords, list):
                        keywords_text = ' '.join(keywords).lower()
                        
                        # Categorize by field
                        for field, terms in field_mapping.items():
                            if any(term in keywords_text for term in terms):
                                field_keywords[field] += 1
                                if session.krt_data:
                                    field_resources[field].extend(session.krt_data)
                except (json.JSONDecodeError, TypeError):
                    continue
        
        # Analyze resource patterns by field
        field_resource_analysis = {}
        for field, resources in field_resources.items():
            resource_types = defaultdict(int)
            for resource in resources:
                res_type = resource.get('RESOURCE TYPE', 'Unknown')
                resource_types[res_type] += 1
            
            field_resource_analysis[field] = {
                'paper_count': field_keywords[field],
                'total_resources': len(resources),
                'avg_resources_per_paper': len(resources) / field_keywords[field] if field_keywords[field] > 0 else 0,
                'top_resource_types': dict(sorted(resource_types.items(), key=lambda x: x[1], reverse=True)[:5])
            }
        
        return {
            'field_distribution': dict(field_keywords),
            'field_resource_analysis': field_resource_analysis
        }
    
    def _get_policy_insights(self):
        """Generate policy-relevant insights"""
        completed_sessions = KRTSession.objects.filter(status='completed', krt_data__isnull=False)
        
        # Resource identification compliance
        total_resources = 0
        resources_with_rrid = 0
        resources_with_any_id = 0
        commercial_without_id = 0
        
        # Reproducibility indicators
        software_with_version = 0
        total_software = 0
        protocols_referenced = 0
        
        for session in completed_sessions:
            if session.krt_data:
                for resource in session.krt_data:
                    total_resources += 1
                    
                    identifier = resource.get('IDENTIFIER', '').lower()
                    source = resource.get('SOURCE', '').lower()
                    res_type = resource.get('RESOURCE TYPE', '').lower()
                    additional_info = resource.get('ADDITIONAL INFORMATION', '').lower()
                    
                    # RRID compliance
                    if 'rrid:' in identifier:
                        resources_with_rrid += 1
                        resources_with_any_id += 1
                    elif identifier not in ['no identifier exists', 'n/a', '', 'none']:
                        resources_with_any_id += 1
                    
                    # Commercial resources without identifiers
                    if any(vendor in source for vendor in ['sigma', 'abcam', 'thermo', 'invitrogen']):
                        if identifier in ['no identifier exists', 'n/a', '', 'none']:
                            commercial_without_id += 1
                    
                    # Software versioning
                    if 'software' in res_type:
                        total_software += 1
                        if any(version_indicator in (identifier + additional_info) 
                              for version_indicator in ['version', 'v.', 'v1', 'v2', 'v3']):
                            software_with_version += 1
                    
                    # Protocol references
                    if 'protocol' in res_type or 'protocol' in source.lower():
                        protocols_referenced += 1
        
        rrid_compliance = (resources_with_rrid / total_resources * 100) if total_resources > 0 else 0
        identification_rate = (resources_with_any_id / total_resources * 100) if total_resources > 0 else 0
        software_versioning_rate = (software_with_version / total_software * 100) if total_software > 0 else 0
        
        return {
            'rrid_compliance_rate': round(rrid_compliance, 1),
            'overall_identification_rate': round(identification_rate, 1),
            'software_versioning_rate': round(software_versioning_rate, 1),
            'commercial_without_id': commercial_without_id,
            'protocols_referenced': protocols_referenced,
            'total_resources_analyzed': total_resources,
            'reproducibility_score': round((rrid_compliance + software_versioning_rate) / 2, 1)
        }
    
    def _get_quality_metrics(self):
        """Analyze quality and reproducibility metrics"""
        completed_sessions = KRTSession.objects.filter(status='completed')
        
        # KRT detection rate
        sessions_with_existing_krt = completed_sessions.filter(existing_krt_detected=True).count()
        krt_detection_rate = (sessions_with_existing_krt / completed_sessions.count() * 100) if completed_sessions.count() > 0 else 0
        
        # Resource extraction efficiency by method
        regex_sessions = completed_sessions.filter(mode='regex')
        llm_sessions = completed_sessions.filter(mode='llm')
        
        regex_avg_resources = regex_sessions.aggregate(Avg('resources_found'))['resources_found__avg'] or 0
        llm_avg_resources = llm_sessions.aggregate(Avg('resources_found'))['resources_found__avg'] or 0
        
        regex_avg_time = regex_sessions.aggregate(Avg('processing_time'))['processing_time__avg'] or 0
        llm_avg_time = llm_sessions.aggregate(Avg('processing_time'))['processing_time__avg'] or 0
        
        return {
            'krt_detection_rate': round(krt_detection_rate, 1),
            'extraction_efficiency': {
                'regex': {
                    'avg_resources': round(regex_avg_resources, 1),
                    'avg_time': round(regex_avg_time, 2),
                    'efficiency_score': round(regex_avg_resources / max(regex_avg_time, 0.1), 2)
                },
                'llm': {
                    'avg_resources': round(llm_avg_resources, 1),
                    'avg_time': round(llm_avg_time, 2),
                    'efficiency_score': round(llm_avg_resources / max(llm_avg_time, 0.1), 2)
                }
            }
        }