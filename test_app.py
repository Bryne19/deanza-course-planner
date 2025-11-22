#!/usr/bin/env python3
"""
Quick test script to verify the app can start
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    print("Testing imports...")
    from flask import Flask
    print("✓ Flask imported")
    
    from models import parse_class_time, detect_conflicts, CourseManager
    print("✓ models imported")
    
    from scraper_module import DeAnzaScheduleScraper
    print("✓ scraper_module imported")
    
    from app import app
    print("✓ app imported")
    
    print("\n✅ All imports successful!")
    print("\nTo start the app, run:")
    print("   python3 run.py")
    print("\nThen open: http://localhost:5001")
    
except ImportError as e:
    print(f"\n❌ Import error: {e}")
    print("\nMake sure you're in the web_app directory and all dependencies are installed:")
    print("   pip3 install flask")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

