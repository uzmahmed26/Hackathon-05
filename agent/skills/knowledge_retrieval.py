"""
Knowledge Retrieval Skill
Fetches correct information from FAQs, documents, or database based on user query.
"""

import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path


class KnowledgeRetrieval:
    def __init__(self, knowledge_base_path: str = "context/product-docs.md"):
        """
        Initialize the knowledge retrieval system with a knowledge base.
        
        Args:
            knowledge_base_path: Path to the knowledge base file
        """
        self.knowledge_base_path = knowledge_base_path
        self.knowledge_base = self._load_knowledge_base()
    
    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """
        Load the knowledge base from the specified file.
        
        Returns:
            List of knowledge base entries
        """
        try:
            # Read the knowledge base file
            with open(self.knowledge_base_path, 'r', encoding='utf-8') as file:
                content = file.read()
                
            # Parse the content into structured entries
            # This is a simplified parsing for markdown FAQ format
            entries = self._parse_faq_format(content)
            return entries
        except FileNotFoundError:
            print(f"Warning: Knowledge base file {self.knowledge_base_path} not found.")
            return []
        except Exception as e:
            print(f"Error loading knowledge base: {str(e)}")
            return []
    
    def _parse_faq_format(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse FAQ format from markdown content.
        
        Args:
            content: Raw content from the knowledge base file
            
        Returns:
            List of parsed FAQ entries
        """
        entries = []
        lines = content.split('\n')
        
        current_title = ""
        current_content = []
        
        for line in lines:
            # Check if line is a header (FAQ question)
            if line.startswith('#'):
                # Save previous entry if exists
                if current_title and current_content:
                    entries.append({
                        'id': len(entries) + 1,
                        'title': current_title,
                        'content': ' '.join(current_content).strip(),
                        'relevance_score': 0.0
                    })
                
                # Start new entry
                # Remove markdown header symbols (#, ##, ###, etc.)
                header_parts = line.split(' ', 1)
                if len(header_parts) > 1:
                    current_title = header_parts[1].strip()
                else:
                    current_title = line.replace('#', '').strip()
                current_content = []
            # Skip empty lines and headers
            elif line.strip() and not line.startswith('##'):
                current_content.append(line.strip())
        
        # Add the last entry
        if current_title and current_content:
            entries.append({
                'id': len(entries) + 1,
                'title': current_title,
                'content': ' '.join(current_content).strip(),
                'relevance_score': 0.0
            })
        
        return entries
    
    def search_knowledge_base(self, query: str, max_results: int = 3, 
                             confidence_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Search the knowledge base for relevant entries based on the query.
        
        Args:
            query: User's question or query text
            max_results: Maximum number of results to return
            confidence_threshold: Minimum confidence score for results
            
        Returns:
            List of relevant knowledge base entries
        """
        # Simple keyword matching algorithm
        query_lower = query.lower()
        results = []
        
        for entry in self.knowledge_base:
            # Calculate relevance score based on keyword matching
            title_lower = entry['title'].lower()
            content_lower = entry['content'].lower()
            
            # Count matches in title and content
            title_matches = len([word for word in query_lower.split() if word in title_lower])
            content_matches = len([word for word in query_lower.split() if word in content_lower])
            
            # Calculate a simple relevance score
            # Title matches are weighted more heavily than content matches
            relevance_score = (title_matches * 0.7) + (content_matches * 0.3)
            
            # Normalize the score (simple normalization based on query length)
            if len(query_lower.split()) > 0:
                relevance_score = relevance_score / len(query_lower.split())
            
            # Apply a simple threshold to filter out very low matches
            if relevance_score > 0:
                results.append({
                    'id': entry['id'],
                    'title': entry['title'],
                    'content': entry['content'],
                    'confidence': min(relevance_score, 1.0),  # Cap at 1.0
                    'source': 'product-docs.md'
                })
        
        # Sort results by confidence score in descending order
        results.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Filter by confidence threshold and limit results
        filtered_results = [r for r in results if r['confidence'] >= confidence_threshold]
        return filtered_results[:max_results]
    
    def get_relevant_entries(self, query: str, context: Optional[str] = None, 
                           max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Main method to retrieve relevant knowledge base entries for a query.
        
        Args:
            query: User's question or query text
            context: Additional context about the customer or situation
            max_results: Maximum number of results to return (default: 3)
            
        Returns:
            List of relevant knowledge base entries
        """
        # Combine query and context if context is provided
        search_query = query
        if context:
            search_query = f"{query} {context}"
        
        # Perform the search
        results = self.search_knowledge_base(search_query, max_results=max_results)
        
        return {
            'results': results,
            'query_understanding': search_query
        }


# Example usage
if __name__ == "__main__":
    # Initialize the knowledge retrieval system
    knowledge_retrieval = KnowledgeRetrieval()
    
    # Example query
    query = "How do I reset my password?"
    result = knowledge_retrieval.get_relevant_entries(query)
    
    print("Query:", query)
    print("Results:")
    for entry in result['results']:
        print(f"- {entry['title']}: {entry['content'][:100]}...")
        print(f"  Confidence: {entry['confidence']:.2f}")