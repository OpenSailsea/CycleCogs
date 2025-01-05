import re
from urllib.parse import urlparse
import ipaddress
from typing import Optional, Tuple, List
import linkvertise

URL_PATTERN = r'(?:https?:\/\/)?(?:[\w-]+\.)+[a-z]{2,}(?:\/[^\s]*)?'

def is_valid_domain(domain: str) -> bool:
    """Check if domain is valid and not in exclusion list"""
    # Exclude localhost
    if domain.lower() == 'localhost':
        return False
        
    # Exclude example.com
    if 'example.com' in domain.lower():
        return False
        
    # Try parsing as IP address
    try:
        ipaddress.ip_address(domain)
        return False  # Is IP address, return False
    except ValueError:
        pass  # Not IP address, continue checking
        
    # Check domain format
    if not re.match(r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z]{2,})+$', domain):
        return False
        
    return True

def extract_urls(text: str) -> List[Tuple[str, int, int]]:
    """
    Extract all valid URLs from text
    Returns: List of (url, start_pos, end_pos) tuples
    """
    urls = []
    for match in re.finditer(URL_PATTERN, text, re.IGNORECASE):
        url = match.group()
        parsed = urlparse(url if '://' in url else f'http://{url}')
        
        if is_valid_domain(parsed.netloc):
            urls.append((url, match.start(), match.end()))
            
    return urls

def convert_to_linkvertise(url: str, client: linkvertise.Client, account_id: int) -> str:
    """Convert URL to Linkvertise link"""
    if not url.startswith(('http://', 'https://')):
        url = f'http://{url}'
    try:
        return client.linkvertise(account_id, url)
    except Exception as e:
        print(f"Linkvertise conversion failed: {e}")
        return url  # Return original URL if conversion fails
