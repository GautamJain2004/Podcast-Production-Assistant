"""
Academic Paper Search Tool

Searches arXiv and PubMed for academic papers related to research topics.
"""

import logging
from typing import List, Dict, Any, Optional
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


class ArxivSearcher:
    """Search arXiv for academic papers."""
    
    BASE_URL = "http://export.arxiv.org/api/query"
    
    @staticmethod
    def search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search arXiv for papers.
        
        Args:
            query: Search query
            max_results: Maximum number of results
        
        Returns:
            List of paper dictionaries
        """
        try:
            params = {
                'search_query': f'all:{query}',
                'start': 0,
                'max_results': max_results,
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }
            
            response = requests.get(ArxivSearcher.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            # Parse XML response
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            # Define namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom',
                  'arxiv': 'http://arxiv.org/schemas/atom'}
            
            papers = []
            for entry in root.findall('atom:entry', ns):
                try:
                    title = entry.find('atom:title', ns)
                    summary = entry.find('atom:summary', ns)
                    published = entry.find('atom:published', ns)
                    link = entry.find('atom:id', ns)
                    
                    # Get authors
                    authors = []
                    for author in entry.findall('atom:author', ns):
                        name = author.find('atom:name', ns)
                        if name is not None and name.text:
                            authors.append(name.text)
                    
                    # Get categories
                    categories = []
                    for category in entry.findall('atom:category', ns):
                        term = category.get('term')
                        if term:
                            categories.append(term)
                    
                    paper = {
                        'title': title.text.strip() if title is not None else 'Unknown',
                        'summary': summary.text.strip() if summary is not None else '',
                        'authors': authors,
                        'published': published.text if published is not None else '',
                        'url': link.text if link is not None else '',
                        'categories': categories,
                        'source': 'arXiv'
                    }
                    papers.append(paper)
                except Exception as e:
                    logger.warning(f"Error parsing arXiv entry: {e}")
                    continue
            
            logger.info(f"Found {len(papers)} papers on arXiv for query: {query}")
            return papers
            
        except Exception as e:
            logger.error(f"Error searching arXiv: {e}")
            return []


class PubMedSearcher:
    """Search PubMed for medical/biological papers."""
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    @staticmethod
    def search(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search PubMed for papers.
        
        Args:
            query: Search query
            max_results: Maximum number of results
        
        Returns:
            List of paper dictionaries
        """
        try:
            # Step 1: Search for PMIDs
            search_url = f"{PubMedSearcher.BASE_URL}/esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': query,
                'retmax': max_results,
                'retmode': 'json',
                'sort': 'relevance'
            }
            
            search_response = requests.get(search_url, params=search_params, timeout=10)
            search_response.raise_for_status()
            search_data = search_response.json()
            
            pmids = search_data.get('esearchresult', {}).get('idlist', [])
            
            if not pmids:
                logger.info(f"No PubMed results found for query: {query}")
                return []
            
            # Step 2: Fetch details for PMIDs
            fetch_url = f"{PubMedSearcher.BASE_URL}/esummary.fcgi"
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(pmids),
                'retmode': 'json'
            }
            
            fetch_response = requests.get(fetch_url, params=fetch_params, timeout=10)
            fetch_response.raise_for_status()
            fetch_data = fetch_response.json()
            
            papers = []
            for pmid in pmids:
                try:
                    article = fetch_data.get('result', {}).get(pmid, {})
                    
                    if not article:
                        continue
                    
                    # Extract authors
                    authors = []
                    for author in article.get('authors', []):
                        name = author.get('name', '')
                        if name:
                            authors.append(name)
                    
                    paper = {
                        'title': article.get('title', 'Unknown'),
                        'summary': article.get('source', ''),  # PubMed doesn't provide full abstract in summary
                        'authors': authors,
                        'published': article.get('pubdate', ''),
                        'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                        'pmid': pmid,
                        'journal': article.get('fulljournalname', ''),
                        'source': 'PubMed'
                    }
                    papers.append(paper)
                except Exception as e:
                    logger.warning(f"Error parsing PubMed entry {pmid}: {e}")
                    continue
            
            logger.info(f"Found {len(papers)} papers on PubMed for query: {query}")
            return papers
            
        except Exception as e:
            logger.error(f"Error searching PubMed: {e}")
            return []


def search_academic_papers(query: str, max_results: int = 10, sources: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Search multiple academic databases.
    
    Args:
        query: Search query
        max_results: Maximum results per source
        sources: List of sources to search ('arxiv', 'pubmed'). Default: both
    
    Returns:
        Dictionary with source names as keys and paper lists as values
    """
    if sources is None:
        sources = ['arxiv', 'pubmed']
    
    results = {}
    
    if 'arxiv' in sources:
        results['arxiv'] = ArxivSearcher.search(query, max_results)
    
    if 'pubmed' in sources:
        results['pubmed'] = PubMedSearcher.search(query, max_results)
    
    return results


def format_paper_for_research(paper: Dict[str, Any]) -> str:
    """
    Format a paper dictionary into a readable research snippet.
    
    Args:
        paper: Paper dictionary from search results
    
    Returns:
        Formatted string for research materials
    """
    authors_str = ", ".join(paper.get('authors', [])[:3])
    if len(paper.get('authors', [])) > 3:
        authors_str += " et al."
    
    formatted = f"""
Title: {paper.get('title', 'Unknown')}
Authors: {authors_str}
Published: {paper.get('published', 'Unknown')}
Source: {paper.get('source', 'Unknown')}
URL: {paper.get('url', '')}

Summary: {paper.get('summary', 'No summary available')[:500]}...
"""
    return formatted.strip()
