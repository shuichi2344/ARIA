"""
Network connectivity checker for ARIA platform.
Tests internet connection and database accessibility.
"""

import socket
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aria.config import get_settings


def check_internet():
    """Check basic internet connectivity."""
    print("🔍 Checking internet connectivity...")
    
    test_hosts = [
        ("8.8.8.8", 53, "Google DNS"),  # Google DNS
        ("1.1.1.1", 53, "Cloudflare DNS"),  # Cloudflare DNS
    ]
    
    for host, port, name in test_hosts:
        try:
            socket.create_connection((host, port), timeout=3)
            print(f"   ✅ Can reach {name} ({host})")
            return True
        except OSError:
            print(f"   ❌ Cannot reach {name} ({host})")
    
    print("\n❌ No internet connection detected!")
    print("   Please check your network connection.")
    return False


def check_dns():
    """Check DNS resolution."""
    print("\n🔍 Checking DNS resolution...")
    
    test_domains = [
        "google.com",
        "cloudflare.com",
    ]
    
    for domain in test_domains:
        try:
            socket.gethostbyname(domain)
            print(f"   ✅ Can resolve {domain}")
            return True
        except socket.gaierror:
            print(f"   ❌ Cannot resolve {domain}")
    
    print("\n❌ DNS resolution is not working!")
    print("   This might be a DNS server issue.")
    return False


def check_supabase():
    """Check Supabase database accessibility via connection pooler."""
    print("\n🔍 Checking Supabase database accessibility (via Pooler)...")
    
    try:
        settings = get_settings()
        supabase_url = str(settings.supabase_url).rstrip("/")
        host = supabase_url.replace("https://", "").replace("http://", "")
        project_ref = host.split(".")[0]
        
        # Use Supabase Connection Pooler — read region from env
        pooler_region = os.getenv("POOLER_REGION", "ap-southeast-1")
        pooler_host = f"aws-0-{pooler_region}.pooler.supabase.com"
        pooler_port = 6543
        
        print(f"   Project ref: {project_ref}")
        print(f"   Pooler host: {pooler_host}")
        print(f"   Pooler port: {pooler_port}")
        
        # Try to resolve hostname
        try:
            addr_info = socket.getaddrinfo(pooler_host, pooler_port, socket.AF_INET, socket.SOCK_STREAM)
            ip_address = addr_info[0][4][0]
            print(f"   ✅ Can resolve pooler hostname to {ip_address}")
        except socket.gaierror as e:
            print(f"   ❌ Cannot resolve pooler hostname: {e}")
            return False
        
        # Try to connect to pooler port
        try:
            sock = socket.create_connection((pooler_host, pooler_port), timeout=5)
            sock.close()
            print(f"   ✅ Can connect to pooler port {pooler_port}")
            return True
        except (socket.timeout, OSError) as e:
            print(f"   ❌ Cannot connect to pooler port {pooler_port}: {e}")
            print(f"   The database pooler might be down or firewall is blocking.")
            return False
            
    except Exception as e:
        print(f"   ❌ Error checking Supabase: {e}")
        return False


def main():
    """Run all network checks."""
    print("=" * 70)
    print("ARIA Network Connectivity Check".center(70))
    print("=" * 70)
    print()
    
    # Check 1: Internet connectivity
    internet_ok = check_internet()
    
    if not internet_ok:
        print("\n" + "=" * 70)
        print("❌ FAILED: No internet connection")
        print("=" * 70)
        print("\n💡 Troubleshooting steps:")
        print("   1. Check if your computer is connected to the internet")
        print("   2. Try opening a website in your browser")
        print("   3. Check if your firewall is blocking connections")
        print("   4. Try disabling VPN if you're using one")
        return
    
    # Check 2: DNS resolution
    dns_ok = check_dns()
    
    if not dns_ok:
        print("\n" + "=" * 70)
        print("❌ FAILED: DNS resolution not working")
        print("=" * 70)
        print("\n💡 Troubleshooting steps:")
        print("   1. Try changing your DNS server to 8.8.8.8 (Google DNS)")
        print("   2. Flush your DNS cache:")
        print("      Windows: ipconfig /flushdns")
        print("      Mac: sudo dscacheutil -flushcache")
        print("      Linux: sudo systemd-resolve --flush-caches")
        return
    
    # Check 3: Supabase accessibility
    supabase_ok = check_supabase()
    
    print("\n" + "=" * 70)
    if supabase_ok:
        print("✅ SUCCESS: All network checks passed!")
        print("=" * 70)
        print("\nYour system can connect to the Supabase database.")
        print("You can now run the ARIA simulation.")
    else:
        print("❌ FAILED: Cannot connect to Supabase database")
        print("=" * 70)
        print("\n💡 Troubleshooting steps:")
        print("   1. Check if Supabase is experiencing an outage:")
        print("      https://status.supabase.com/")
        print("   2. Verify your .env file has the correct SUPABASE_URL")
        print("   3. Check if your firewall is blocking port 5432")
        print("   4. Try accessing Supabase dashboard in your browser")


if __name__ == "__main__":
    main()
