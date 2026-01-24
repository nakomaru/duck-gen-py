# duck-gen-py

A Python CLI tool to generate [DuckDuckGo Email Protection](https://spreadprivacy.com/protect-your-inbox-with-duckduckgo-email-protection/) private addresses.

Ported from [duck-gen (Go)](https://github.com/chowder/duck-gen).

## Features
- **Auto-Copy:** Copies new address to clipboard.
- **Persistent Login:** Saves token locally (`.duck_token`), auto-refreshes if expired.
- **Trustworthy:** Open source, simple, uses standard libraries.

## Usage

1. **Install:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run:**
   ```bash
   python duck_gen.py
   ```

3. Enter your duck.com email address.

4. Enter the one time passphrase from your email.

5. The new alias will be shown in the console and automatically copied to your clipboard.
