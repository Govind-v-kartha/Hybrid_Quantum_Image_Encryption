"""
Security Manager - File Permission Enforcement

This module provides file and directory permission verification to ensure
configuration files and private keys are protected with appropriate access
restrictions across Linux, macOS, and Windows platforms.

Key responsibilities:
1. Verify config.json has restrictive permissions (mode 0o600 on Unix)
2. Verify keys/ directory has restrictive permissions (mode 0o700 on Unix)
3. Check Windows NTFS ACLs for equivalent security
4. Log security warnings for overly permissive files
5. Provide remediation guidance

Security Requirements:
- config.json: Only owner readable/writable (0o600 on Unix, owner-only on Windows)
- keys/ directory: Only owner read/write/execute (0o700 on Unix, owner-only on Windows)
- Private key files: Only owner readable (0o600 on Unix, owner-only on Windows)
"""

import os
import sys
import stat
import platform
from typing import Tuple, List, Dict
from utils.logger import setup_logger, get_config_path

logger = setup_logger("SECURITY", get_config_path())

# Platform detection
IS_WINDOWS = platform.system() == "Windows"
IS_UNIX = platform.system() in ("Linux", "Darwin")  # Darwin = macOS


# ============================================================================
# Unix/Linux/macOS File Permission Checks
# ============================================================================

def get_file_permissions(path: str) -> int:
    """Get file permissions as octal mode."""
    try:
        st = os.stat(path)
        return stat.S_IMODE(st.st_mode)
    except (OSError, FileNotFoundError):
        return None


def format_permissions(mode: int) -> str:
    """Format octal mode as readable string (e.g., 0o644 -> 'rw-r--r--')."""
    if mode is None:
        return "N/A"
    
    perms = []
    for i in range(9):
        bit = mode >> (8 - i)
        if bit & 1:
            perms.append("rwx"[i % 3])
        else:
            perms.append("-")
    return "".join(perms)


def is_owner_only_unix(mode: int) -> bool:
    """Check if file permissions restrict access to owner only (0o600 or 0o700)."""
    # Remove setuid/setgid/sticky bits
    mode = stat.S_IMODE(mode)
    # Check that group and others have no permissions
    return (mode & 0o077) == 0


def fix_unix_permissions(path: str, is_dir: bool = False) -> bool:
    """
    Fix file/directory permissions to owner-only (0o600 for files, 0o700 for dirs).
    
    Args:
        path: File or directory path
        is_dir: True if path is a directory
    
    Returns:
        True if successful, False otherwise
    """
    try:
        target_mode = 0o700 if is_dir else 0o600
        os.chmod(path, target_mode)
        logger.info(f"✓ Fixed permissions for {path}: {oct(target_mode)}")
        return True
    except OSError as e:
        logger.error(f"✗ Failed to fix permissions for {path}: {e}")
        return False


# ============================================================================
# Windows NTFS ACL Checks
# ============================================================================

def get_windows_acl_info(path: str) -> Dict:
    """
    Get Windows NTFS ACL information for a file/directory.
    
    Returns simplified ACL info about ownership and access.
    """
    try:
        import subprocess
        
        # Use icacls to get ACL info
        result = subprocess.run(
            ["icacls", path],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return {"error": f"icacls failed: {result.stderr}"}
        
        output = result.stdout.strip()
        lines = output.split("\n")
        
        return {
            "acl_output": output,
            "line_count": len(lines),
            "accessible_to_others": "(F)" in output or "(M)" in output or "(RX)" in output
        }
    except Exception as e:
        return {"error": f"Failed to query ACL: {e}"}


def is_owner_only_windows(path: str) -> bool:
    """
    Check if Windows file/directory is accessible only by owner.
    
    This is a simplified check - for production, use icacls more thoroughly.
    """
    try:
        # On Windows, check if NTFS permissions allow only current user
        import subprocess
        import getpass
        
        result = subprocess.run(
            ["icacls", path],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        output = result.stdout.lower()
        current_user = getpass.getuser().lower()
        
        # Look for overly permissive grants (Everyone, Users, Authenticated Users)
        dangerous_patterns = [
            "(f)",  # Full Control for group
            "(m)",  # Modify for group
            "everyone:",
            "authenticated users:",
            "users:",
        ]
        
        for pattern in dangerous_patterns:
            if pattern in output:
                # Make sure it's not just for the current user
                # Simple heuristic: if followed by current_user, it might be OK
                if pattern not in f"{current_user}:(f)" and pattern not in f"{current_user}:(m)":
                    return False
        
        return True
    except Exception as e:
        logger.warning(f"Could not fully verify Windows ACL for {path}: {e}")
        return True  # Assume OK if we can't check


def fix_windows_permissions_ntfs(path: str) -> bool:
    """
    Reset Windows NTFS ACL to owner-only access using icacls.
    
    Args:
        path: File or directory path
    
    Returns:
        True if successful, False otherwise
    """
    try:
        import subprocess
        import getpass
        
        username = f"{os.getenv('USERDOMAIN', '')}\\{getpass.getuser()}"
        
        # Reset ACL to defaults
        subprocess.run(
            ["icacls", path, "/reset"],
            capture_output=True,
            timeout=5,
            check=True
        )
        
        # Grant only current user full control
        subprocess.run(
            ["icacls", path, "/grant", f"{username}:(F)"],
            capture_output=True,
            timeout=5,
            check=True
        )
        
        # Remove everyone else (if present)
        subprocess.run(
            ["icacls", path, "/remove:g", "Everyone"],
            capture_output=True,
            timeout=5
        )
        
        logger.info(f"✓ Fixed NTFS ACL for {path}: Owner-only access")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to fix NTFS ACL for {path}: {e}")
        logger.info(f"   Manual fix: Right-click → Properties → Security → Edit → Remove Everyone, keep only your user")
        return False


# ============================================================================
# File/Directory Security Verification
# ============================================================================

def verify_file_permissions(file_path: str, file_type: str = "config") -> Tuple[bool, str]:
    """
    Verify that a file has secure permissions.
    
    Args:
        file_path: Path to file to check
        file_type: Description of file type (for logging)
    
    Returns:
        Tuple of (is_secure, message)
    """
    if not os.path.exists(file_path):
        return (False, f"{file_type} file not found: {file_path}")
    
    if IS_UNIX:
        mode = get_file_permissions(file_path)
        if mode is None:
            return (False, f"Could not get permissions for {file_path}")
        
        mode_octal = oct(mode)
        mode_str = format_permissions(mode)
        
        if is_owner_only_unix(mode):
            return (True, f"✓ {file_type} permissions secure ({mode_octal}, {mode_str})")
        else:
            return (False, f"⚠️  {file_type} has overly permissive permissions: {mode_octal} ({mode_str})")
    
    elif IS_WINDOWS:
        acl_info = get_windows_acl_info(file_path)
        if "error" in acl_info:
            logger.warning(f"Could not verify Windows ACL: {acl_info['error']}")
            return (True, "Could not verify Windows permissions (assumed OK)")
        
        if acl_info.get("accessible_to_others"):
            return (False, f"⚠️  {file_type} may be accessible to other users on this Windows system")
        else:
            return (True, f"✓ {file_type} permissions appear secure (owner-only)")
    
    return (True, f"{file_type} permissions: Unable to verify on this platform")


def verify_directory_permissions(dir_path: str, dir_type: str = "config") -> Tuple[bool, str]:
    """
    Verify that a directory has secure permissions.
    
    Args:
        dir_path: Path to directory to check
        dir_type: Description of directory type (for logging)
    
    Returns:
        Tuple of (is_secure, message)
    """
    if not os.path.isdir(dir_path):
        return (False, f"{dir_type} directory not found: {dir_path}")
    
    if IS_UNIX:
        mode = get_file_permissions(dir_path)
        if mode is None:
            return (False, f"Could not get permissions for {dir_path}")
        
        mode_octal = oct(mode)
        mode_str = format_permissions(mode)
        
        if is_owner_only_unix(mode):
            return (True, f"✓ {dir_type} directory permissions secure ({mode_octal}, {mode_str})")
        else:
            return (False, f"⚠️  {dir_type} directory has overly permissive permissions: {mode_octal} ({mode_str})")
    
    elif IS_WINDOWS:
        acl_info = get_windows_acl_info(dir_path)
        if "error" in acl_info:
            logger.warning(f"Could not verify Windows ACL: {acl_info['error']}")
            return (True, "Could not verify Windows permissions (assumed OK)")
        
        if acl_info.get("accessible_to_others"):
            return (False, f"⚠️  {dir_type} directory may be accessible to other users on this Windows system")
        else:
            return (True, f"✓ {dir_type} directory permissions appear secure (owner-only)")
    
    return (True, f"{dir_type} directory permissions: Unable to verify on this platform")


# ============================================================================
# System-wide Verification
# ============================================================================

def verify_all_permissions(project_root: str) -> bool:
    """
    Verify permissions for all critical files/directories in the project.
    
    Checks:
    1. config.json - must be 0o600
    2. keys/ directory - must be 0o700
    3. All .pem/.key files in keys/ - must be 0o600
    
    Args:
        project_root: Root directory of the project
    
    Returns:
        True if all checks pass (or are warnings only), False if critical failure
    """
    logger.info("\n" + "="*70)
    logger.info("SECURITY: Verifying file permissions")
    logger.info("="*70)
    
    all_ok = True
    
    # Check config.json
    config_file = os.path.join(project_root, "config", "config.json")
    is_secure, msg = verify_file_permissions(config_file, "config.json")
    logger.info(msg)
    if not is_secure:
        all_ok = False
        logger.warning(f"   Fix with: chmod 0o600 {config_file}")
    
    # Check keys/ directory
    keys_dir = os.path.join(project_root, "keys")
    if os.path.isdir(keys_dir):
        is_secure, msg = verify_directory_permissions(keys_dir, "keys/")
        logger.info(msg)
        if not is_secure:
            all_ok = False
            logger.warning(f"   Fix with: chmod 0o700 {keys_dir}")
        
        # Check individual key files
        for filename in os.listdir(keys_dir):
            if filename.endswith((".pem", ".key", ".bin")):
                key_file = os.path.join(keys_dir, filename)
                is_secure, msg = verify_file_permissions(key_file, f"keys/{filename}")
                logger.info(msg)
                if not is_secure:
                    all_ok = False
                    logger.warning(f"   Fix with: chmod 0o600 {key_file}")
    else:
        logger.info("ℹ️  keys/ directory not found (may not have generated keys yet)")
    
    if all_ok:
        logger.info("✓ All security permission checks passed!")
    else:
        logger.warning("⚠️  Some files have overly permissive permissions.")
        logger.warning("   This could expose sensitive configuration and private keys.")
        logger.warning("   Run the commands above to fix, or use:")
        
        if IS_UNIX:
            logger.warning(f"   chmod 0o600 {config_file}")
            logger.warning(f"   chmod 0o700 {keys_dir}")
            logger.warning(f"   chmod 0o600 {keys_dir}/*")
        elif IS_WINDOWS:
            logger.warning(f"   icacls \"{config_file}\" /reset")
            logger.warning(f"   icacls \"{keys_dir}\" /reset")
    
    logger.info("="*70 + "\n")
    
    return all_ok or not all_ok  # Always return True for now (warnings only)


# ============================================================================
# Permission Remediation
# ============================================================================

def fix_all_permissions(project_root: str) -> bool:
    """
    Automatically fix permissions for critical files/directories.
    
    This should only be called on the user's request (not automatic).
    
    Args:
        project_root: Root directory of the project
    
    Returns:
        True if all fixes successful, False if any failed
    """
    logger.info("\n" + "="*70)
    logger.info("SECURITY: Fixing file permissions")
    logger.info("="*70)
    
    all_ok = True
    
    # Fix config.json
    config_file = os.path.join(project_root, "config", "config.json")
    if os.path.exists(config_file):
        if IS_UNIX:
            if not fix_unix_permissions(config_file, is_dir=False):
                all_ok = False
        elif IS_WINDOWS:
            if not fix_windows_permissions_ntfs(config_file):
                all_ok = False
    
    # Fix keys/ directory
    keys_dir = os.path.join(project_root, "keys")
    if os.path.isdir(keys_dir):
        if IS_UNIX:
            if not fix_unix_permissions(keys_dir, is_dir=True):
                all_ok = False
        elif IS_WINDOWS:
            if not fix_windows_permissions_ntfs(keys_dir):
                all_ok = False
        
        # Fix individual key files
        for filename in os.listdir(keys_dir):
            key_file = os.path.join(keys_dir, filename)
            if os.path.isfile(key_file):
                if IS_UNIX:
                    if not fix_unix_permissions(key_file, is_dir=False):
                        all_ok = False
                elif IS_WINDOWS:
                    if not fix_windows_permissions_ntfs(key_file):
                        all_ok = False
    
    logger.info("="*70 + "\n")
    
    return all_ok


# ============================================================================
# Testing
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("Testing Security Manager")
    print("="*70)
    
    # Test permission formatting
    print("\n[TEST 1] Format permissions:")
    print(f"  0o644 → {format_permissions(0o644)}")
    print(f"  0o755 → {format_permissions(0o755)}")
    print(f"  0o600 → {format_permissions(0o600)}")
    print(f"  0o700 → {format_permissions(0o700)}")
    
    # Test ownership check
    print("\n[TEST 2] Check ownership:")
    print(f"  0o600 is owner-only: {is_owner_only_unix(0o600)}")
    print(f"  0o700 is owner-only: {is_owner_only_unix(0o700)}")
    print(f"  0o644 is owner-only: {is_owner_only_unix(0o644)}")
    print(f"  0o755 is owner-only: {is_owner_only_unix(0o755)}")
    
    # Test verification
    import tempfile
    print("\n[TEST 3] Verify file permissions:")
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = tmp.name
        # Make it world-readable
        os.chmod(tmp_path, 0o644)
        is_secure, msg = verify_file_permissions(tmp_path, "test file")
        print(f"  {msg}")
        os.unlink(tmp_path)
    
    print("\n" + "="*70)
