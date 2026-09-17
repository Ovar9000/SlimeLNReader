"""
Launcher for AnyFlip Local Light Novel Viewer
Starts the local server and automatically opens the viewer in the browser.
"""
import os
import sys
import socket
import webbrowser
import threading
import time
from server import start_server

def find_available_port(start_port=8080, max_attempts=50):
    """Find an available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

def main():
    use_app_window = "--app" in sys.argv
    port = find_available_port(8080)
    server = start_server(port)
    url = f"http://127.0.0.1:{port}/index.html"

    # Start server in daemon thread
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    print("=" * 60)
    print("  📖 AnyFlip / FlipHTML5 Local Light Novel Viewer")
    print("  Volume 22: Godly Destruction and Chaos")
    print("=" * 60)
    print(f"  Server URL: {url}")
    print("  Press Ctrl+C in this terminal to stop the server.")
    print("=" * 60)

    if use_app_window:
        try:
            import webview
            print("Launching native desktop window via pywebview...")
            webview.create_window(
                "Tensura Volume 22 - Light Novel Flipbook",
                url,
                width=1280,
                height=860,
                min_size=(800, 600)
            )
            webview.start()
            return
        except ImportError:
            print("pywebview not available, falling back to default browser.")

    # Open in default browser
    time.sleep(0.4)
    webbrowser.open(url)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Flipbook server. Happy reading!")

if __name__ == "__main__":
    main()
