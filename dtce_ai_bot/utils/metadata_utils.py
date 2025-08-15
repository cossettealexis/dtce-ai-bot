"""
Utility functions for handling metadata in Azure Blob Storage.
"""


def sanitize_metadata_value(value):
    """
    Convert metadata value to ASCII-safe string for Azure Blob Storage.
    
    Azure Blob Storage metadata values must be ASCII strings. This function
    handles Unicode characters by replacing them with '?' or underscores.
    
    Args:
        value: The metadata value to sanitize
        
    Returns:
        ASCII-safe string
    """
    if not value:
        return ""
    
    # Convert to string first
    str_value = str(value)
    
    # Try to encode/decode to ASCII, replacing non-ASCII characters
    try:
        # Use 'replace' error handling to replace non-ASCII chars with '?'
        return str_value.encode('ascii', errors='replace').decode('ascii')
    except Exception:
        # Fallback: manually replace all non-ASCII with underscore
        return ''.join(c if ord(c) < 128 else '_' for c in str_value)


def sanitize_metadata_dict(metadata_dict):
    """
    Sanitize all values in a metadata dictionary for Azure Blob Storage.
    
    Args:
        metadata_dict: Dictionary of metadata key-value pairs
        
    Returns:
        Dictionary with all values sanitized to ASCII
    """
    return {
        key: sanitize_metadata_value(value) if key != "is_critical" and key != "is_folder" and key != "is_folder_marker" 
        else value  # Keep boolean flags as-is
        for key, value in metadata_dict.items()
    }
