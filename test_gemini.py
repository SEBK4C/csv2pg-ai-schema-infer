#!/usr/bin/env python3
"""Quick test script to verify Gemini API configuration."""

import os
import sys
from pathlib import Path

# Load environment variables from .env
from dotenv import load_dotenv

def test_gemini_api():
    """Test Gemini API connection with clear error messages."""

    # Load .env file
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        print("❌ Error: .env file not found")
        print(f"   Expected location: {env_path}")
        print("   Please create a .env file with your GEMINI_API_KEY")
        return False

    load_dotenv(env_path)

    # Check for API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.strip() == "":
        print("❌ Error: GEMINI_API_KEY is not set or is empty")
        print(f"   Please add your API key to: {env_path}")
        print("   Format: GEMINI_API_KEY=your_api_key_here")
        print("\n   Get your API key from: https://makersuite.google.com/app/apikey")
        return False

    # Check for model name
    model = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
    print(f"✓ Using model: {model}")
    print(f"✓ API key found: {api_key[:8]}...{api_key[-4:]}")

    # Test API connection
    try:
        import google.generativeai as genai
    except ImportError:
        print("\n❌ Error: google-generativeai package not installed")
        print("   Run: uv sync")
        return False

    try:
        genai.configure(api_key=api_key)
        model_instance = genai.GenerativeModel(model)

        print("\n🔄 Testing API connection...")
        response = model_instance.generate_content("Hello, respond with just 'OK' if you can read this.")

        print(f"✅ API connection successful!")
        print(f"   Response: {response.text.strip()}")
        return True

    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ API Error: {error_msg}")

        if "API_KEY_INVALID" in error_msg or "invalid" in error_msg.lower():
            print("\n   Your API key appears to be invalid.")
            print("   Please check:")
            print("   1. The key is copied correctly (no extra spaces)")
            print("   2. The key is active at https://makersuite.google.com/app/apikey")
            print("   3. You haven't exceeded quota limits")
        elif "quota" in error_msg.lower():
            print("\n   You may have exceeded your API quota.")
            print("   Check your usage at: https://makersuite.google.com/")
        elif "not found" in error_msg.lower() or "model" in error_msg.lower():
            print(f"\n   The model '{model}' may not be available.")
            print("   Try setting GEMINI_MODEL=gemini-1.5-flash in .env")

        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Gemini API Configuration Test")
    print("=" * 60 + "\n")

    success = test_gemini_api()

    print("\n" + "=" * 60)
    sys.exit(0 if success else 1)