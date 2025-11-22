#!/usr/bin/env python3
"""
Simple runner script for the Flask app
Handles port conflicts gracefully
"""

import sys
import socket
from app import app

def find_free_port(start_port=5001):
    """Find a free port starting from start_port"""
    for port in range(start_port, start_port + 10):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return None

if __name__ == '__main__':
    # Try to get port from command line argument
    port = 5001
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port: {sys.argv[1]}. Using default port 5001.")
    
    # Check if port is available, find free port if not
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', port))
    except OSError:
        print(f"⚠️  Port {port} is already in use.")
        free_port = find_free_port(port)
        if free_port:
            print(f"   Using port {free_port} instead.")
            port = free_port
        else:
            print(f"   Could not find a free port. Please free up port {port} or specify a different port.")
            sys.exit(1)
    
    print(f"\n🚀 Starting Flask app on http://localhost:{port}")
    print(f"   Press Ctrl+C to stop\n")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        sys.exit(0)

