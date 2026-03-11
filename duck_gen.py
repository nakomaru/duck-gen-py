import os
import sys
import json
import subprocess
import venv
from pathlib import Path
from typing import Optional

def ensure_venv():
    """Ensure the script runs in a virtual environment with required dependencies."""
    # Check if we are already in a virtual environment
    if sys.prefix != sys.base_prefix:
        return

    script_dir = Path(__file__).parent.resolve()
    venv_dir = script_dir / f".venv_{Path(__file__).stem}"
    
    # Platform-specific venv python executable
    if os.name == "nt":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"

    if not venv_python.exists():
        print(f"Creating virtual environment in {venv_dir}...")
        try:
            venv.create(venv_dir, with_pip=True)
        except Exception as e:
            print(f"Failed to create virtual environment: {e}")
            sys.exit(1)
    
    # Check if requirements are satisfied
    try:
        subprocess.check_call([str(venv_python), "-c", "import requests, pyperclip"], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        print("Installing dependencies (requests, pyperclip)...")
        try:
            subprocess.check_call([str(venv_python), "-m", "pip", "install", "requests", "pyperclip"], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print(f"Failed to install dependencies: {e}")
            sys.exit(1)

    # Relaunch script using venv python
    try:
        os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:])
    except AttributeError:
        # os.execv is not always available or behaves differently on some platforms (like Windows in some contexts)
        # fallback to subprocess.run if execv fails or is unavailable
        sys.exit(subprocess.call([str(venv_python), str(Path(__file__).resolve())] + sys.argv[1:]))

# Run bootstrap before anything else
ensure_venv()

# Now we can safely import non-standard libraries
try:
    import requests
    import pyperclip
except ImportError:
    # This might happen if the bootstrap failed to install them but somehow continued
    print("Error: Required dependencies (requests, pyperclip) not found in virtual environment.")
    sys.exit(1)

# Constants
API_BASE = "https://quack.duckduckgo.com/api"
USER_AGENT = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
TOKEN_FILE_NAME = ".duck_token"

class DuckGenError(Exception):
    """Custom exception for DuckGen errors."""
    pass

class TokenExpiredError(DuckGenError):
    """Raised when the API returns 401 Unauthorized."""
    pass

def get_client() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session

def get_token_file() -> Path:
    # Stored in the same directory as the script
    return Path(__file__).parent.resolve() / TOKEN_FILE_NAME

def read_token() -> Optional[str]:
    token_file = get_token_file()
    if token_file.exists():
        try:
            return token_file.read_text().strip()
        except Exception as e:
            print(f"Warning: Could not read token file: {e}")
            return None
    return None

def save_token(token: str) -> None:
    token_file = get_token_file()
    try:
        token_file.write_text(token)
        try:
            os.chmod(token_file, 0o600)
        except OSError:
            pass 
    except Exception as e:
        print(f"Warning: Could not save token: {e}")

def delete_token() -> None:
    token_file = get_token_file()
    if token_file.exists():
        try:
            token_file.unlink()
            print("Invalid/Expired token removed.")
        except Exception as e:
            print(f"Warning: Could not delete token file: {e}")

def get_login_link(user: str) -> None:
    session = get_client()
    url = f"{API_BASE}/auth/loginlink"
    try:
        response = session.get(url, params={"user": user})
        response.raise_for_status()
    except requests.RequestException as e:
        raise DuckGenError(f"Error requesting login link: {e}")

def get_login(user: str, otp: str) -> str:
    session = get_client()
    url = f"{API_BASE}/auth/login"
    try:
        response = session.get(url, params={"user": user, "otp": otp})
        response.raise_for_status()
        data = response.json()
        return data.get("token")
    except requests.RequestException as e:
        raise DuckGenError(f"Error logging in: {e}")
    except json.JSONDecodeError:
        raise DuckGenError("Error parsing login response")

def get_dashboard(otp_token: str) -> str:
    session = get_client()
    url = f"{API_BASE}/email/dashboard"
    session.headers.update({"Authorization": f"Bearer {otp_token}"})
    try:
        response = session.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get("user", {}).get("access_token")
    except requests.RequestException as e:
        raise DuckGenError(f"Error accessing dashboard: {e}")
    except json.JSONDecodeError:
        raise DuckGenError("Error parsing dashboard response")

def generate_address(access_token: str) -> str:
    session = get_client()
    url = f"{API_BASE}/email/addresses"
    session.headers.update({"Authorization": f"Bearer {access_token}"})
    try:
        response = session.post(url)
        
        if response.status_code == 401:
            raise TokenExpiredError("Token is expired or invalid.")
            
        response.raise_for_status()
        data = response.json()
        
        if data.get("error"):
             raise DuckGenError(f"API Error: {data['error']}")
             
        return data.get("address") + "@duck.com"
        
    except requests.RequestException as e:
        # Check if it was a 401 wrapped in an exception (rare with raise_for_status handled above)
        if isinstance(e, requests.HTTPError) and e.response.status_code == 401:
            raise TokenExpiredError("Token is expired or invalid.")
        raise DuckGenError(f"Error generating address: {e}")
    except json.JSONDecodeError:
         raise DuckGenError("Error parsing generate address response")

def get_new_token() -> str:
    print("\n--- duck-gen Setup ---")
    print("Enter your Duck Address (e.g., user@duck.com): ", end="", flush=True)
    duck_address = sys.stdin.readline().strip()
    if not duck_address:
        raise DuckGenError("Duck address cannot be empty.")
    
    username = duck_address.replace("@duck.com", "")
    
    print("Requesting login link...")
    get_login_link(username)
    
    print(f"Check your email ({username}@duck.com) for the passphrase.")
    print("Enter the passphrase: ", end="", flush=True)
    otp = sys.stdin.readline().strip()
    if not otp:
        raise DuckGenError("Passphrase cannot be empty.")
        
    print("Verifying passphrase...")
    login_token = get_login(username, otp)
    if not login_token:
         raise DuckGenError("Could not retrieve login token.")

    print("Retrieving access token...")
    access_token = get_dashboard(login_token)
    if not access_token:
         raise DuckGenError("Could not retrieve access token.")
         
    return access_token

def main():
    try:
        # Main logic loop
        token = read_token()
        address = None
        
        # If we have a token, try to use it first
        if token:
            try:
                print("Using existing token...")
                address = generate_address(token)
            except TokenExpiredError:
                print("Token expired. Re-authenticating...")
                token = None # Force re-auth
                delete_token()
            except DuckGenError as e:
                # Other errors (network, etc) might be fatal or temporary
                print(f"Error: {e}")
                # We don't necessarily want to wipe token for network errors
                pass

        # If no token (or it expired and was cleared), get a new one
        if not address and not token:
            try:
                token = get_new_token()
                save_token(token)
                address = generate_address(token)
            except DuckGenError as e:
                 print(f"Authentication/Generation failed: {e}")

        # Final Result
        if address:
            print(f"\nGenerated: {address}")
            try:
                pyperclip.copy(address)
                print("(Copied to clipboard!)")
            except Exception as e:
                print(f"(Failed to copy to clipboard: {e})")
        else:
            print("\nFailed to generate an address.")

    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
