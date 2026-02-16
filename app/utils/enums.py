"""Utility functions for handling enum/string values safely."""
from enum import Enum


def enum_to_str(v):
    """
    Safely convert enum or string value to string.
    
    Args:
        v: Can be Enum, string, or any value
        
    Returns:
        str: String representation of the value
        
    Examples:
        >>> enum_to_str(Role.ADMIN)
        'ADMIN'
        >>> enum_to_str('ADMIN')
        'ADMIN'
        >>> enum_to_str(None)
        None
    """
    if v is None:
        return None
    if isinstance(v, Enum):
        return v.value
    return str(v)