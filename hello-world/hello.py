#!/usr/bin/env python3
"""Simple hello world HTTP server."""

import os
from http.server import HTTPServer, BaseHTTPRequestHandler

class HelloHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Hello World\n')
    
    def do_POST(self):
        self.do_GET()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HelloHandler)
    print(f'Starting server on port {port}...')
    server.serve_forever()

