from pathlib import Path
import re
from typing import Union

def slugify(value: str) -> str:
    """
    Normalizes a string: converts to lowercase, removes non-alpha characters,
    and converts dashes and spaces to underscores.
    
    Args:
        value: String to be slugified
        
    Returns:
        str: Slugified string
    """
    # Convert to lowercase and strip whitespace
    value = value.strip().lower()
    
    # Remove non-alpha characters (except spaces and dashes)
    value = re.sub(r"[^\w\s-]", "", value)
    
    # Convert spaces or dashes to underscores
    value = re.sub(r"[-\s]+", "_", value)
    
    # Remove non-ASCII characters
    value = re.sub(r"[^\x00-\x7f]", "", value)
    
    return value

def get_filename(file_path: Union[str, Path]) -> str:
    """
    Returns the filename without the filetype extension.
    
    Args:
        file_path: Path to the file (string or Path object)
        
    Returns:
        str: Filename without extension
    
    Examples:
        >>> get_filename("path/to/file.txt")
        'file'
        >>> get_filename(Path("path/to/file.txt"))
        'file'
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
    return file_path.stem
