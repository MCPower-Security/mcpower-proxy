"""String utility functions"""


def truncate_at(text: str, max_length: int) -> str:
    """
    Truncate string at max_length, appending '...' only if truncated.
    
    Args:
        text: String to truncate
        max_length: Maximum length before truncation
        
    Returns:
        Truncated string with '...' suffix if truncated, original if not
    """
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}..."
