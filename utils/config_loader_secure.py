"""
Secure Configuration Loader with Environment Variable Substitution

This module provides secure loading of configuration with automatic
environment variable substitution, preventing secrets from being
stored in plaintext in config.json.

Usage:
    from utils.config_loader_secure import load_config_secure
    
    config = load_config_secure()
    passphrase = config['key_protection']['passphrase']
    # Returns actual passphrase from ENCRYPTION_PASSPHRASE env var
"""

import os
import json
import re
from typing import Any, Dict
from utils.logger import setup_logger, get_config_path

logger = setup_logger("CONFIG", get_config_path())

# Try to import python-dotenv for .env file support
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False
    logger.debug("python-dotenv not installed - .env file support disabled")


def substitute_environment_variables(obj: Any) -> Any:
    """
    Recursively substitute ${VAR_NAME} patterns with environment variable values.
    
    Pattern: ${ENVIRONMENT_VARIABLE_NAME}
    
    Examples:
        "${ENCRYPTION_PASSPHRASE}" → "actual-passphrase-from-env"
        "${RECIPIENT_PRIVATE_KEY_PATH}" → "/path/to/key"
        "fixed_string" → "fixed_string" (no substitution)
    
    Args:
        obj: Any Python object (dict, list, string, etc.)
    
    Returns:
        Object with all ${...} patterns substituted
    """
    if isinstance(obj, dict):
        # Recursively process all dict values
        return {key: substitute_environment_variables(value) for key, value in obj.items()}
    
    elif isinstance(obj, list):
        # Recursively process all list items
        return [substitute_environment_variables(item) for item in obj]
    
    elif isinstance(obj, str):
        # Look for ${VAR_NAME} pattern
        pattern = r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}'
        
        def replace_var(match):
            var_name = match.group(1)
            env_value = os.getenv(var_name)
            
            if env_value is None:
                # Environment variable not set - check if it's optional
                optional_vars = {
                    'RECIPIENT_PRIVATE_KEY_PATH': 'Recipient ML-KEM private key (needed for decryption)',
                    'SENDER_PRIVATE_KEY_PATH': 'Sender ML-DSA private key (needed for encryption)',
                }
                
                if var_name in optional_vars:
                    logger.warning(
                        f"⚠️  Environment variable not set: {var_name}\n"
                        f"   Required for: {optional_vars[var_name]}\n"
                        f"   Set with: export {var_name}=<path>\n"
                        f"   Using original placeholder: ${{{var_name}}}"
                    )
                else:
                    logger.warning(
                        f"⚠️  Environment variable not found: {var_name}\n"
                        f"   Using original placeholder: ${{{var_name}}}"
                    )
                return match.group(0)  # Return original ${VAR_NAME}
            else:
                logger.debug(f"✓ Environment variable substituted: {var_name}")
                return env_value
        
        return re.sub(pattern, replace_var, obj)
    
    else:
        # Return other types as-is
        return obj


def load_env_file(env_path: str = None) -> bool:
    """
    Load environment variables from .env file using python-dotenv.
    
    This function:
    1. Looks for .env file (or custom path)
    2. Loads variables into os.environ
    3. Returns success status
    
    Args:
        env_path: Custom path to .env file (default: .env in project root)
    
    Returns:
        True if .env was loaded, False if not found or dotenv unavailable
    """
    if not DOTENV_AVAILABLE:
        logger.debug("python-dotenv not available - skipping .env file loading")
        return False
    
    if env_path is None:
        # Default: look for .env in project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(project_root, '.env')
    
    if not os.path.exists(env_path):
        logger.debug(f"No .env file found at {env_path}")
        return False
    
    try:
        load_dotenv(env_path, override=False)  # Don't override existing env vars
        logger.info(f"✓ Loaded environment variables from {env_path}")
        return True
    except Exception as e:
        logger.warning(f"⚠️  Failed to load .env file: {e}")
        return False


def load_config_secure(config_path: str = None, env_path: str = None) -> Dict[str, Any]:
    """
    Load configuration from JSON file with environment variable substitution.
    
    This function:
    1. Loads .env file (if python-dotenv available)
    2. Loads config.json
    3. Recursively substitutes ${ENV_VAR} patterns
    4. Returns fully resolved configuration
    
    Environment variables supported:
        ENCRYPTION_PASSPHRASE — Scrypt/AES passphrase for key protection (CRITICAL)
        RECIPIENT_PRIVATE_KEY_PATH — ML-KEM private key for decryption
        SENDER_PRIVATE_KEY_PATH — ML-DSA private key for encryption
    
    Args:
        config_path: Custom path to config.json (default: config/config.json)
        env_path: Custom path to .env file (default: .env in project root)
    
    Returns:
        Dictionary with full configuration and all env vars substituted
    
    Raises:
        FileNotFoundError: If config file not found
        json.JSONDecodeError: If config is not valid JSON
        
    Examples:
        >>> config = load_config_secure()
        >>> config['key_protection']['passphrase']
        'passphrase-from-env'
    """
    # First, try to load .env file to populate environment
    load_env_file(env_path)
    
    if config_path is None:
        # Default: look for config.json in config/ directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, 'config', 'config.json')
    
    # Resolve to absolute path
    if not os.path.isabs(config_path):
        config_path = os.path.abspath(config_path)
    
    logger.info(f"Loading configuration: {config_path}")
    
    # Check file exists
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    # Load JSON
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.debug(f"✓ Configuration loaded successfully ({len(config)} sections)")
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in config file: {e}")
        raise
    
    # Substitute environment variables
    logger.debug("Substituting environment variables...")
    config = substitute_environment_variables(config)
    
    # Verify critical secrets were substituted
    _verify_secrets_substituted(config)
    
    logger.info("✓ Configuration loaded with environment variable substitution")
    return config


def _verify_secrets_substituted(config: Dict[str, Any]) -> None:
    """
    Verify that critical secrets were properly substituted.
    
    Checks that:
    1. Passphrase is not the literal string "${ENCRYPTION_PASSPHRASE}"
    2. Key paths are resolved (if enabled)
    3. All required values are present
    
    Args:
        config: Loaded configuration dictionary
        
    Warns if:
    - Passphrase still contains ${...} pattern (env var not set)
    - Private key paths still contain ${...} pattern (env var not set)
    """
    key_protection = config.get('key_protection', {})
    post_quantum = config.get('post_quantum', {})
    metadata_sig = config.get('metadata_signature', {})
    
    # Check passphrase
    passphrase = key_protection.get('passphrase', '')
    if passphrase.startswith('${') and passphrase.endswith('}'):
        logger.critical(
            "🚨 CRITICAL: Passphrase not set!\n"
            f"   Set environment variable: {passphrase[2:-1]}\n"
            f"   Example: export {passphrase[2:-1]}=\"your-strong-passphrase\"\n"
            f"   Encryption/decryption will FAIL without this."
        )
    elif passphrase == 'change-this-passphrase-in-production':
        logger.warning(
            "⚠️  WARNING: Using default passphrase!\n"
            "   This is INSECURE. Set a strong passphrase via environment variable.\n"
            "   See ENVIRONMENT_SETUP.md for details."
        )
    
    # Check recipient private key path (needed for decryption)
    if post_quantum.get('enabled'):
        recipient_key_path = post_quantum.get('recipient_private_key_path', '')
        if recipient_key_path.startswith('${') and recipient_key_path.endswith('}'):
            logger.warning(
                f"⚠️  Recipient ML-KEM private key path not set (needed for decryption)\n"
                f"   Set environment variable: {recipient_key_path[2:-1]}\n"
                f"   Example: export {recipient_key_path[2:-1]}=\"/path/to/keys/recipient_kyber768_private.key\""
            )
    
    # Check sender private key path (needed for encryption)
    if metadata_sig.get('enabled'):
        sender_key_path = metadata_sig.get('sender_private_key_path', '')
        if sender_key_path.startswith('${') and sender_key_path.endswith('}'):
            logger.warning(
                f"⚠️  Sender ML-DSA private key path not set (needed for encryption)\n"
                f"   Set environment variable: {sender_key_path[2:-1]}\n"
                f"   Example: export {sender_key_path[2:-1]}=\"/path/to/keys/sender_dilithium3_private.key\""
            )


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Backward compatibility wrapper for load_config_secure().
    
    This maintains API compatibility with existing code that calls load_config().
    All new code should use load_config_secure() directly.
    
    Args:
        config_path: Custom path to config.json
    
    Returns:
        Configuration dictionary with environment variables substituted
    """
    return load_config_secure(config_path)


# ============================================================================
# Testing
# ============================================================================

if __name__ == '__main__':
    # Manual testing
    print("\n" + "="*70)
    print("Testing Secure Config Loader")
    print("="*70)
    
    # Test 1: Load with env vars
    print("\n[TEST 1] Load with environment variables")
    os.environ['ENCRYPTION_PASSPHRASE'] = 'test-passphrase-123'
    os.environ['RECIPIENT_PRIVATE_KEY_PATH'] = '/test/recipient/key'
    
    try:
        cfg = load_config_secure()
        print(f"✓ Passphrase: {cfg['key_protection']['passphrase']}")
        print(f"✓ Recipient key path: {cfg['post_quantum']['recipient_private_key_path']}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 2: Verify substitution
    print("\n[TEST 2] Verify substitution")
    test_dict = {
        "passphrase": "${TEST_VAR}",
        "nested": {
            "value": "${ANOTHER_VAR}"
        },
        "list": ["${VAR1}", "${VAR2}"]
    }
    
    os.environ['TEST_VAR'] = 'test-value'
    os.environ['ANOTHER_VAR'] = 'nested-value'
    os.environ['VAR1'] = 'list-value-1'
    os.environ['VAR2'] = 'list-value-2'
    
    result = substitute_environment_variables(test_dict)
    print(f"✓ Substituted: {result}")
    
    print("\n" + "="*70)
