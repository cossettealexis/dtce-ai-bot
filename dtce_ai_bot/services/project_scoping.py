"""
Project Scoping and Similarity Analysis Service.
Analyzes new project requests, finds similar past projects, and provides design guidance.
"""

import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
import structlog
from azure.search.documents import SearchClient
from openai import AsyncAzureOpenAI
from ..config.settings import get_settings

logger = structlog.get_logger(__name__)


class ProjectScopingService:
    """Service for analyzing project scopes and finding similar past projects."""
    
    def __init__(self, search_client: SearchClient):
        """Initialize the project scoping service."""
        self.search_client = search_client
        settings = get_settings()
        
        # Initialize Azure OpenAI client
        self.openai_client = AsyncAzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version
        )
        
        self.model_name = settings.azure_openai_deployment_name
        
    async def analyze_project_request(self, request_text: str) -> Dict[str, Any]:
        """
        Analyze a project request and find similar past projects.
        
        Args:
            request_text: The client's project request text
            
        Returns:
            Dictionary with analysis, similar projects, recommendations, and warnings
        """
        try:
            logger.info("Analyzing project request")
            
            # Step 1: Extract key project characteristics
            project_characteristics = await self._extract_project_characteristics(request_text)
            
            # Step 2: Find similar past projects
            similar_projects = await self._find_similar_projects(project_characteristics)
            
            # Step 3: Generate comprehensive analysis with past experience
            analysis = await self._generate_project_analysis(
                request_text, 
                project_characteristics, 
                similar_projects
            )
            
            return {
                "project_characteristics": project_characteristics,
                "similar_projects": similar_projects,
                "analysis": analysis,
                "status": "success"
            }
            
        except Exception as e:
            logger.error("Error analyzing project request", error=str(e))
            return {
                "error": str(e),
                "status": "error"
            }
    
    async def _extract_project_characteristics(self, request_text: str) -> Dict[str, Any]:
        """Extract key characteristics from the project request."""
        
        extraction_prompt = f"""
        Analyze this project request and extract key engineering characteristics:
        
        REQUEST:
        {request_text}
        
        Extract and categorize:
        1. PROJECT TYPE: (building, structure, infrastructure, etc.)
        2. STRUCTURAL ELEMENTS: (marquee, building, bridge, etc.)
        3. DIMENSIONS: (size, height, area)
        4. LOCATION: (city, region, environmental conditions)
        5. LOADS & FORCES: (wind loads, seismic, live loads)
        6. MATERIALS: (steel, concrete, timber, fabric)
        7. FOUNDATION/FIXING: (concrete pad, ground anchors, etc.)
        8. COMPLIANCE REQUIREMENTS: (PS1, PS3, building consent, etc.)
        9. ENVIRONMENTAL CONDITIONS: (wind zones, soil conditions)
        10. SPECIAL CONSIDERATIONS: (temporary, permanent, access, etc.)
        
        Provide a structured JSON response with these categories.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are an expert structural engineer analyzing project requirements. Extract key technical characteristics in JSON format."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse the JSON response (simplified for now)
            content = response.choices[0].message.content
            
            # Extract key info using regex patterns as fallback
            characteristics = {
                "project_type": self._extract_project_type(request_text),
                "dimensions": self._extract_dimensions(request_text),
                "location": self._extract_location(request_text),
                "loads": self._extract_loads(request_text),
                "compliance": self._extract_compliance(request_text),
                "materials": self._extract_materials(request_text),
                "raw_analysis": content
            }
            
            return characteristics
            
        except Exception as e:
            logger.error("Error extracting project characteristics", error=str(e))
            return {"error": str(e)}
    
    async def _find_similar_projects(self, characteristics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar past projects based on extracted characteristics."""
        
        # Build search queries based on characteristics
        search_terms = []
        
        if characteristics.get("project_type"):
            search_terms.append(characteristics["project_type"])
        if characteristics.get("dimensions"):
            search_terms.append(characteristics["dimensions"])
        if characteristics.get("location"):
            search_terms.append(characteristics["location"])
        if characteristics.get("compliance"):
            search_terms.append(characteristics["compliance"])
        
        # Search for similar projects
        search_query = " ".join(search_terms)
        
        try:
            # Perform semantic search for similar projects
            results = self.search_client.search(
                search_text=search_query,
                select=["title", "content", "project", "file_path", "chunk_id"],
                top=10,
                search_mode="semantic"
            )
            
            similar_projects = []
            for result in results:
                similarity_score = getattr(result, "@search.score", 0)
                if similarity_score > 0.7:  # Threshold for similarity
                    similar_projects.append({
                        "title": result.get("title", ""),
                        "content": result.get("content", "")[:500],  # Limit content
                        "project": result.get("project", ""),
                        "file_path": result.get("file_path", ""),
                        "similarity_score": similarity_score
                    })
            
            return similar_projects[:5]  # Return top 5 most similar
            
        except Exception as e:
            logger.error("Error finding similar projects", error=str(e))
            return []
    
    async def _generate_project_analysis(
        self, 
        request_text: str, 
        characteristics: Dict[str, Any], 
        similar_projects: List[Dict[str, Any]]
    ) -> str:
        """Generate comprehensive project analysis with past experience insights."""
        
        # Prepare context from similar projects
        past_experience = "\n".join([
            f"SIMILAR PROJECT: {proj.get('title', 'Unknown')}\n"
            f"Content: {proj.get('content', '')}\n"
            f"Project: {proj.get('project', '')}\n"
            f"Similarity: {proj.get('similarity_score', 0):.2f}\n"
            for proj in similar_projects
        ])
        
        analysis_prompt = f"""
        As a senior structural engineer at DTCE, analyze this new project request and provide comprehensive guidance based on our past experience:

        NEW PROJECT REQUEST:
        {request_text}

        PROJECT CHARACTERISTICS EXTRACTED:
        {characteristics}

        SIMILAR PAST PROJECTS FROM OUR DATABASE:
        {past_experience}

        Please provide a comprehensive analysis covering:

        1. **PROJECT OVERVIEW & CLASSIFICATION**
           - Project type and complexity assessment
           - Key structural elements and challenges

        2. **SIMILAR PAST PROJECTS ANALYSIS**
           - Which past projects are most relevant and why
           - Key similarities and differences
           - Lessons learned from those projects

        3. **DESIGN PHILOSOPHY & APPROACH**
           - Recommended design approach based on past experience
           - Critical design considerations
           - Load path analysis recommendations

        4. **PAST ISSUES & SOLUTIONS**
           - Common issues we've encountered on similar projects
           - How we solved those issues
           - Preventive measures to implement

        5. **COMPLIANCE & CERTIFICATION GUIDANCE**
           - PS1/PS3 requirements and approach
           - Building consent considerations
           - Documentation requirements

        6. **RISK ASSESSMENT & WARNINGS**
           - Potential challenges based on past experience
           - Areas requiring special attention
           - Early warning signs to watch for

        7. **RECOMMENDATIONS & NEXT STEPS**
           - Information still needed from client
           - Site investigation requirements
           - Design verification steps

        8. **COST & TIMELINE INSIGHTS**
           - Typical costs for similar projects
           - Timeline expectations
           - Factors that could affect budget/schedule

        Provide specific, actionable advice based on our documented past experience.
        """
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a senior structural engineer at DTCE with extensive experience in similar projects. Provide detailed, practical guidance based on documented past projects and lessons learned."
                    },
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("Error generating project analysis", error=str(e))
            return f"Error generating analysis: {str(e)}"
    
    def _extract_project_type(self, text: str) -> str:
        """Extract project type from text."""
        types = ["marquee", "building", "bridge", "structure", "grandstand", "roof", "warehouse"]
        text_lower = text.lower()
        for proj_type in types:
            if proj_type in text_lower:
                return proj_type
        return "unknown"
    
    def _extract_dimensions(self, text: str) -> str:
        """Extract dimensions from text."""
        # Look for patterns like "15x40m", "15m x 40m", etc.
        dimension_pattern = r'(\d+)\s*[xX×]\s*(\d+)\s*m'
        matches = re.findall(dimension_pattern, text)
        if matches:
            return f"{matches[0][0]}x{matches[0][1]}m"
        return ""
    
    def _extract_location(self, text: str) -> str:
        """Extract location from text."""
        locations = ["wellington", "auckland", "christchurch", "hamilton", "tauranga", "dunedin", "trentham"]
        text_lower = text.lower()
        for location in locations:
            if location in text_lower:
                return location.title()
        return ""
    
    def _extract_loads(self, text: str) -> str:
        """Extract load information from text."""
        # Look for wind loads, seismic, etc.
        load_pattern = r'(\d+)\s*kph|(\d+)\s*km/h|wind load|seismic|live load'
        matches = re.findall(load_pattern, text.lower())
        loads = []
        if "wind" in text.lower():
            wind_match = re.search(r'(\d+)\s*kph|(\d+)\s*km/h', text)
            if wind_match:
                speed = wind_match.group(1) or wind_match.group(2)
                loads.append(f"wind {speed}kph")
        return ", ".join(loads)
    
    def _extract_compliance(self, text: str) -> str:
        """Extract compliance requirements from text."""
        compliance_terms = ["ps1", "ps3", "certification", "building consent", "compliance"]
        text_lower = text.lower()
        found = [term for term in compliance_terms if term in text_lower]
        return ", ".join(found)
    
    def _extract_materials(self, text: str) -> str:
        """Extract materials from text."""
        materials = ["steel", "concrete", "timber", "fabric", "aluminum", "pvc"]
        text_lower = text.lower()
        found = [material for material in materials if material in text_lower]
        return ", ".join(found)


# Service instance
project_scoping_service = None

def get_project_scoping_service() -> ProjectScopingService:
    """Get the global project scoping service instance."""
    global project_scoping_service
    if project_scoping_service is None:
        from ..integrations.azure_search import get_search_client
        search_client = get_search_client()
        project_scoping_service = ProjectScopingService(search_client)
    return project_scoping_service
