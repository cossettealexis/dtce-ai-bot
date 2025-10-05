"""
Project folder structure parser
Handles: Projects/225/225221 where 225 = year 2025, 225221 = job number
"""
import re
from typing import Optional, Dict


def parse_project_path(folder_path: str) -> Optional[Dict[str, str]]:
    """
    Parse project folder structure to extract year and job number.
    
    Examples:
        "Projects/225/225221" -> {year: "2025", job_number: "225221", year_code: "225"}
        "Project/225/225221"  -> {year: "2025", job_number: "225221", year_code: "225"}
        "Clients/Company/Jobs/225221" -> {year: "2025", job_number: "225221", year_code: "225"}
    
    Pattern: Any 6-digit number starting with 2 digits (year code)
    """
    # Look for 6-digit job numbers (e.g., 225221, 219208, 220134)
    job_match = re.search(r'\b(2\d{2})(\d{3})\b', folder_path)
    
    if job_match:
        year_code = job_match.group(1)  # First 3 digits (e.g., "225")
        job_number = job_match.group(0)  # Full 6 digits (e.g., "225221")
        
        # Convert year code to full year
        # 219 -> 2019, 220 -> 2020, 225 -> 2025
        year_suffix = year_code[1:]  # "25" from "225"
        full_year = f"20{year_suffix}"
        
        return {
            "year": full_year,
            "year_code": year_code,
            "job_number": job_number,
            "display_name": f"Job {job_number} ({full_year})"
        }
    
    return None


def extract_project_from_blob_path(blob_name: str) -> str:
    """
    Extract project information from blob storage path.
    Returns formatted project name or "Company Documents" if not a project.
    
    Examples:
        "Projects/225/225221/file.pdf" -> "Job 225221 (2025)"
        "Clients/ABC/Jobs/225221/file.pdf" -> "Job 225221 (2025)"
        "Company Documents/file.pdf" -> "Company Documents"
    """
    project_info = parse_project_path(blob_name)
    
    if project_info:
        return project_info["display_name"]
    
    # Fallback: check for common company document folders
    if any(folder in blob_name for folder in ["Company Documents", "Technical Library", "Standards", "Policies"]):
        # Extract the main folder name
        parts = blob_name.split('/')
        if len(parts) > 0:
            return parts[0]
    
    return "Company Documents"


def is_project_document(blob_name: str) -> bool:
    """Check if a document belongs to a project (has job number)."""
    return parse_project_path(blob_name) is not None
