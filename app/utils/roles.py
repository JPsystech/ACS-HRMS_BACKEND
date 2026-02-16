"""
Role utility functions for handling both enum and string role values
"""

def role_name(role):
    """
    Safely extract role name from either enum or string
    
    Args:
        role: Either a Role enum instance or a string
        
    Returns:
        str: The role name as string
    """
    return role.value if hasattr(role, "value") else str(role)