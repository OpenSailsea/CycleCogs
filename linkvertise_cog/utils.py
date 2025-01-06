import re
from urllib.parse import urlparse
import ipaddress
from typing import Optional, Tuple, List
import linkvertise
import aiohttp
import json

URL_PATTERN = r'(?:https?:\/\/)?(?:[\w-]+\.)+[a-z]{2,}(?:\/[^\s]*)?'

async def create_shortio_link(url: str, api_key: str, domain: str) -> Optional[str]:
    """Create a short link using Short.io API
    
    Args:
        url: Original URL to shorten
        api_key: Short.io API key
        domain: Short.io custom domain
        
    Returns:
        Shortened URL if successful, None otherwise
    """
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": api_key
    }
    
    payload = {
        "originalURL": url,
        "domain": domain,
        "allowDuplicates": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.short.io/links", json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("shortURL")
    except Exception as e:
        print(f"Short.io API error: {e}")
    return None

def is_valid_domain(domain: str, whitelisted_domains: List[str] = None) -> bool:
    """Check if domain is valid and not in exclusion list
    
    Args:
        domain: Domain to check
        whitelisted_domains: List of whitelisted domains
        
    Returns:
        True if domain is valid and not whitelisted, False otherwise
    """
    # Check whitelist
    if whitelisted_domains and domain.lower() in [d.lower() for d in whitelisted_domains]:
        return False
        
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

def extract_urls(text: str, whitelisted_domains: List[str] = None) -> List[Tuple[str, int, int]]:
    """Extract all valid URLs from text
    
    Args:
        text: Text to extract URLs from
        whitelisted_domains: List of whitelisted domains
        
    Returns:
        List of tuples containing (url, start_pos, end_pos)
    """
    urls = []
    for match in re.finditer(URL_PATTERN, text, re.IGNORECASE):
        url = match.group()
        parsed = urlparse(url if '://' in url else f'http://{url}')
        
        if is_valid_domain(parsed.netloc, whitelisted_domains):
            urls.append((url, match.start(), match.end()))
            
    return urls

async def convert_to_linkvertise(url: str, client: linkvertise.LinkvertiseClient, account_id: int, shortio_api_key: Optional[str] = None, shortio_domain: Optional[str] = None) -> str:
    """Convert URL to Linkvertise link
    
    Args:
        url: URL to convert
        client: Linkvertise client instance
        account_id: Linkvertise account ID
        shortio_api_key: Optional Short.io API key
        shortio_domain: Optional Short.io domain
        
    Returns:
        Converted URL (may be shortened if Short.io is configured)
    """
    if not url.startswith(('http://', 'https://')):
        url = f'http://{url}'
    try:
        linkvertise_url = client.linkvertise(account_id, url)
        
        # If Short.io is configured, convert further
        if shortio_api_key and shortio_domain:
            shortened_url = await create_shortio_link(linkvertise_url, shortio_api_key, shortio_domain)
            if shortened_url:
                return shortened_url
                
        return linkvertise_url
    except Exception as e:
        print(f"Linkvertise conversion failed: {e}")
        return url  # Return original URL if conversion fails
