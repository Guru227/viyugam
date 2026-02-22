import socket
import os
import subprocess
import signal
import sys
import time
import re

def find_free_port(start_port):
    """Finds the first available port starting from start_port."""
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
            port += 1
    raise RuntimeError("No free ports found")

def update_frontend_env(backend_port):
    """Updates web/.env.local with the correct API URL."""
    env_path = 'web/.env.local'
    api_url = f"http://localhost:{backend_port}/api/v1"
    key = "NEXT_PUBLIC_API_URL"
    
    content = ""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            content = f.read()
    
    # Simple regex replacement or append
    if key in content:
        content = re.sub(f'{key}=.*', f'{key}={api_url}', content)
    else:
        if content and not content.endswith('\n'):
            content += '\n'
        content += f'{key}={api_url}\n'

    with open(env_path, 'w') as f:
        f.write(content)
    print(f"✅ Updated {env_path}: {key}={api_url}")

def main():
    print("🚀 Starting Viyugam Dev Environment...")
    
    # 1. Find Backend Port
    backend_port = find_free_port(8000)
    print(f"📍 Selected Backend Port: {backend_port}")
    
    # 2. Update Frontend Config
    update_frontend_env(backend_port)
    
    # 3. Start Backend
    print("🐍 Launching Backend...")
    backend_cmd = [
        ".venv/bin/python", "-m", "uvicorn", 
        "app.main:app", "--reload", "--port", str(backend_port)
    ]
    # Run in backend dir so relative paths work if needed
    backend_proc = subprocess.Popen(backend_cmd, cwd="backend")
    
    # 4. Start Frontend
    print("⚛️  Launching Frontend...")
    # Next.js automatically finds a free port starting from 3000
    frontend_cmd = ["npm", "run", "dev"]
    frontend_proc = subprocess.Popen(frontend_cmd, cwd="web")
    
    print("\n✨ Both services are running!")
    print("   - Press Ctrl+C to stop both.")
    
    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
        backend_proc.terminate()
        frontend_proc.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
