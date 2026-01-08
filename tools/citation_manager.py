"""
Citation Manager

Manages academic citations and source attribution for podcast content.
Tracks which sources are used where and generates proper citations.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class Citation:
    """Represents a single citation with full metadata."""
    
    def __init__(
        self,
        source_id: str,
        title: str,
        url: str,
        source_type: str = "web",
        authors: List[str] = None,
        published_date: str = None,
        accessed_date: str = None,
        journal: str = None,
        doi: str = None,
        arxiv_id: str = None,
        pmid: str = None
    ):
        self.source_id = source_id
        self.title = title
        self.url = url
        self.source_type = source_type  # web, youtube, arxiv, pubmed
        self.authors = authors or []
        self.published_date = published_date
        self.accessed_date = accessed_date or datetime.now().strftime("%Y-%m-%d")
        self.journal = journal
        self.doi = doi
        self.arxiv_id = arxiv_id
        self.pmid = pmid
        self.used_in_sections: Set[str] = set()  # Track where this citation is used
        self.quote_count = 0  # Track how many times it's referenced
    
    def to_apa_format(self) -> str:
        """Generate APA-style citation."""
        parts = []
        
        # Authors
        if self.authors:
            if len(self.authors) == 1:
                parts.append(f"{self.authors[0]}.")
            elif len(self.authors) == 2:
                parts.append(f"{self.authors[0]} & {self.authors[1]}.")
            else:
                parts.append(f"{self.authors[0]} et al.")
        else:
            parts.append("Unknown Author.")
        
        # Date
        year = self._extract_year(self.published_date) if self.published_date else "n.d."
        parts.append(f"({year}).")
        
        # Title
        parts.append(f"{self.title}.")
        
        # Source-specific formatting
        if self.source_type == "arxiv":
            if self.arxiv_id:
                parts.append(f"arXiv preprint arXiv:{self.arxiv_id}.")
        elif self.source_type == "pubmed":
            if self.journal:
                parts.append(f"{self.journal}.")
            if self.pmid:
                parts.append(f"PMID: {self.pmid}.")
        elif self.source_type == "youtube":
            parts.append("[Video].")
        
        # URL
        parts.append(f"Retrieved from {self.url}")
        
        return " ".join(parts)
    
    def to_mla_format(self) -> str:
        """Generate MLA-style citation."""
        parts = []
        
        # Authors
        if self.authors:
            if len(self.authors) == 1:
                parts.append(f"{self.authors[0]}.")
            else:
                parts.append(f"{self.authors[0]}, et al.")
        else:
            parts.append("Unknown Author.")
        
        # Title
        parts.append(f'"{self.title}."')
        
        # Source
        if self.journal:
            parts.append(f"{self.journal},")
        
        # Date
        if self.published_date:
            parts.append(f"{self.published_date}.")
        
        # URL
        parts.append(f"{self.url}.")
        
        # Access date
        parts.append(f"Accessed {self.accessed_date}.")
        
        return " ".join(parts)
    
    def to_chicago_format(self) -> str:
        """Generate Chicago-style citation."""
        parts = []
        
        # Authors
        if self.authors:
            parts.append(f"{self.authors[0]}.")
        else:
            parts.append("Unknown Author.")
        
        # Title
        parts.append(f'"{self.title}."')
        
        # Publication info
        if self.journal:
            parts.append(f"{self.journal}")
        
        if self.published_date:
            parts.append(f"({self.published_date}).")
        
        # URL
        parts.append(f"{self.url}.")
        
        return " ".join(parts)
    
    def to_inline_citation(self) -> str:
        """Generate inline citation for use in text."""
        if self.authors and self.published_date:
            author = self.authors[0].split()[-1] if self.authors else "Unknown"
            year = self._extract_year(self.published_date)
            return f"({author}, {year})"
        elif self.authors:
            author = self.authors[0].split()[-1]
            return f"({author})"
        else:
            return f"(Source {self.source_id})"
    
    def _extract_year(self, date_str: str) -> str:
        """Extract year from date string."""
        if not date_str:
            return "n.d."
        match = re.search(r'\d{4}', date_str)
        return match.group(0) if match else "n.d."
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type,
            "authors": self.authors,
            "published_date": self.published_date,
            "accessed_date": self.accessed_date,
            "journal": self.journal,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "pmid": self.pmid,
            "used_in_sections": list(self.used_in_sections),
            "quote_count": self.quote_count,
            "citations": {
                "apa": self.to_apa_format(),
                "mla": self.to_mla_format(),
                "chicago": self.to_chicago_format(),
                "inline": self.to_inline_citation()
            }
        }


class CitationManager:
    """Manages all citations for a podcast episode."""
    
    def __init__(self):
        self.citations: Dict[str, Citation] = {}
        self.citation_counter = 0
        self.logger = logging.getLogger(__name__)
    
    def add_citation_from_research_material(self, material: Any) -> str:
        """
        Add a citation from a ResearchMaterial object.
        Returns the citation ID.
        """
        self.citation_counter += 1
        source_id = f"ref{self.citation_counter}"
        
        # Extract metadata based on source type
        source_type = getattr(material, "source", "web")
        title = getattr(material, "title", "Unknown Title")
        url = getattr(material, "url", "")
        
        # Parse authors and dates from title or content
        authors = self._extract_authors(material)
        published_date = self._extract_date(material)
        
        # Extract academic identifiers
        arxiv_id = self._extract_arxiv_id(url)
        pmid = self._extract_pmid(url)
        doi = self._extract_doi(url)
        
        # Only determine source type from title/URL if not already set
        if source_type == "web":
            # Try to detect more specific type
            if "[VIDEO]" in title or "youtube.com" in url or "youtu.be" in url:
                source_type = "youtube"
            elif "[PAPER]" in title or arxiv_id:
                source_type = "arxiv"
            elif pmid or "pubmed" in url:
                source_type = "pubmed"
        
        citation = Citation(
            source_id=source_id,
            title=title.replace("[VIDEO] ", "").replace("[PAPER] ", ""),
            url=url,
            source_type=source_type,
            authors=authors,
            published_date=published_date,
            arxiv_id=arxiv_id,
            pmid=pmid,
            doi=doi
        )
        
        self.citations[source_id] = citation
        self.logger.debug(f"Added citation {source_id}: {title[:50]}...")
        
        return source_id
    
    def mark_citation_used(self, source_id: str, section: str = "main") -> None:
        """Mark a citation as used in a specific section."""
        if source_id in self.citations:
            self.citations[source_id].used_in_sections.add(section)
            self.citations[source_id].quote_count += 1
    
    def get_citation(self, source_id: str) -> Optional[Citation]:
        """Get a citation by ID."""
        return self.citations.get(source_id)
    
    def get_all_citations(self) -> List[Citation]:
        """Get all citations."""
        return list(self.citations.values())
    
    def get_used_citations(self) -> List[Citation]:
        """Get only citations that were actually used."""
        return [c for c in self.citations.values() if c.quote_count > 0]
    
    def generate_bibliography(self, style: str = "apa", only_used: bool = True) -> str:
        """
        Generate a formatted bibliography.
        
        Args:
            style: Citation style (apa, mla, chicago)
            only_used: Only include citations that were actually used
        """
        citations = self.get_used_citations() if only_used else self.get_all_citations()
        
        if not citations:
            return "No sources cited."
        
        # Sort by author or title
        citations.sort(key=lambda c: c.authors[0] if c.authors else c.title)
        
        lines = ["## References\n"]
        
        for citation in citations:
            if style == "apa":
                formatted = citation.to_apa_format()
            elif style == "mla":
                formatted = citation.to_mla_format()
            elif style == "chicago":
                formatted = citation.to_chicago_format()
            else:
                formatted = citation.to_apa_format()
            
            lines.append(f"[{citation.source_id}] {formatted}\n")
        
        return "\n".join(lines)
    
    def generate_sources_by_type(self) -> Dict[str, List[Citation]]:
        """Group citations by source type."""
        by_type: Dict[str, List[Citation]] = {
            "web": [],
            "youtube": [],
            "arxiv": [],
            "pubmed": []
        }
        
        for citation in self.get_used_citations():
            by_type[citation.source_type].append(citation)
        
        return by_type
    
    def generate_detailed_sources_report(self) -> str:
        """Generate a detailed report of all sources used."""
        by_type = self.generate_sources_by_type()
        
        lines = ["# Detailed Sources Report\n"]
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"Total sources: {len(self.get_used_citations())}\n\n")
        
        for source_type, citations in by_type.items():
            if not citations:
                continue
            
            type_name = {
                "web": "Web Articles",
                "youtube": "YouTube Videos",
                "arxiv": "arXiv Papers",
                "pubmed": "PubMed Papers"
            }.get(source_type, source_type.title())
            
            lines.append(f"## {type_name} ({len(citations)})\n")
            
            for citation in citations:
                lines.append(f"### [{citation.source_id}] {citation.title}\n")
                if citation.authors:
                    lines.append(f"**Authors:** {', '.join(citation.authors)}\n")
                if citation.published_date:
                    lines.append(f"**Published:** {citation.published_date}\n")
                lines.append(f"**URL:** {citation.url}\n")
                if citation.used_in_sections:
                    lines.append(f"**Used in:** {', '.join(citation.used_in_sections)}\n")
                lines.append(f"**Referenced:** {citation.quote_count} time(s)\n")
                
                # Add academic identifiers
                if citation.arxiv_id:
                    lines.append(f"**arXiv ID:** {citation.arxiv_id}\n")
                if citation.pmid:
                    lines.append(f"**PMID:** {citation.pmid}\n")
                if citation.doi:
                    lines.append(f"**DOI:** {citation.doi}\n")
                
                lines.append("\n")
        
        return "\n".join(lines)
    
    def to_json(self) -> Dict[str, Any]:
        """Export all citations to JSON format."""
        return {
            "total_citations": len(self.citations),
            "used_citations": len(self.get_used_citations()),
            "generated_at": datetime.now().isoformat(),
            "citations": [c.to_dict() for c in self.get_all_citations()],
            "by_type": {
                source_type: len(citations)
                for source_type, citations in self.generate_sources_by_type().items()
            }
        }
    
    # Helper methods for extraction
    
    def _extract_authors(self, material: Any) -> List[str]:
        """Extract authors from research material."""
        # Check if content has author information
        content = getattr(material, "content", "")
        
        # Look for "Authors:" pattern
        match = re.search(r'Authors?:\s*([^\n]+)', content)
        if match:
            authors_str = match.group(1)
            # Split by common delimiters
            authors = re.split(r',\s*|\s+and\s+|\s+&\s+', authors_str)
            return [a.strip() for a in authors if a.strip()][:3]  # Max 3 authors
        
        return []
    
    def _extract_date(self, material: Any) -> Optional[str]:
        """Extract publication date from research material."""
        content = getattr(material, "content", "")
        
        # Look for "Published:" pattern
        match = re.search(r'Published:\s*([^\n]+)', content)
        if match:
            return match.group(1).strip()
        
        # Look for year patterns
        match = re.search(r'\b(20\d{2})\b', content)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_arxiv_id(self, url: str) -> Optional[str]:
        """Extract arXiv ID from URL."""
        match = re.search(r'arxiv\.org/abs/(\d+\.\d+)', url)
        return match.group(1) if match else None
    
    def _extract_pmid(self, url: str) -> Optional[str]:
        """Extract PubMed ID from URL."""
        match = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url)
        return match.group(1) if match else None
    
    def _extract_doi(self, url: str) -> Optional[str]:
        """Extract DOI from URL."""
        match = re.search(r'doi\.org/(10\.\d+/[^\s]+)', url)
        return match.group(1) if match else None
