import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import looker_sdk
from looker_sdk import models40
from lkr.load_test.utils import (
    MAX_SESSION_LENGTH,
    PERMISSIONS,
    get_user_id,
)
import sys

sdk = looker_sdk.init40()

class CookielessEmbedHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, debug=False, **kwargs):
        self.debug = debug
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        # Override to disable default server logging
        pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html_path = Path(__file__).parent / "embed_container.html"
            with open(html_path, "r") as f:
                html_content = f.read()
            
            looker_host = os.environ.get("LOOKERSDK_BASE_URL", "")
            html_content = html_content.replace("{{LOOKER_HOST}}", looker_host)
            html_content = html_content.replace("{{debug}}", str(self.debug).lower())

            self.wfile.write(html_content.encode("utf-8"))
        elif self.path == '/acquire-embed-session':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()

            user_id = get_user_id()
            user_session = models40.EmbedCookielessSessionAcquire(
                first_name="Embed",
                last_name=user_id,
                external_user_id=user_id,
                session_length=3600,
                permissions=PERMISSIONS,
                models=["basic_ecomm"],
                # group_ids=["5"],
                external_group_id="test_group_1"
            )

            try:
                response = sdk.acquire_embed_cookieless_session(
                    body=user_session,
                    transport_options={'headers':{'User-Agent': self.headers.get('User-Agent')}}
                )
                self.wfile.write(json.dumps({
                    'api_token': response.api_token,
                    'api_token_ttl': response.api_token_ttl,
                    'authentication_token': response.authentication_token,
                    'authentication_token_ttl': response.authentication_token_ttl,
                    'navigation_token': response.navigation_token,
                    'navigation_token_ttl': response.navigation_token_ttl,
                    'session_reference_token': response.session_reference_token,
                    'session_reference_token_ttl': response.session_reference_token_ttl,
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/generate-embed-tokens':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            session_reference_token = data.get('session_reference_token')
            api_token = data.get('api_token')
            navigation_token = data.get('navigation_token')

            if not session_reference_token or not api_token or not navigation_token:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'session_reference_token, api_token, and navigation_token are required'}).encode('utf-8'))
                return

            try:
                session_information = models40.EmbedCookielessSessionGenerateTokens(
                    session_reference_token=session_reference_token,
                    api_token=api_token,
                    navigation_token=navigation_token
                )
                response = sdk.generate_tokens_for_cookieless_session(
                    body=session_information,
                    transport_options={'headers':{'User-Agent': self.headers.get('User-Agent')}}
                )
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'api_token': response.api_token,
                    'navigation_token': response.navigation_token,
                }).encode('utf-8'))
            except Exception as e:
                print(e)
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=8080, debug=False):
    def handler(*args, **kwargs):
        CookielessEmbedHandler(*args, debug=debug, **kwargs)

    server_address = ('' , port)
    httpd = HTTPServer(server_address, handler)
    httpd.serve_forever()

if __name__ == '__main__':
    port = 8080
    debug = "--debug" in sys.argv
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port number", file=sys.stderr)
            sys.exit(1)
    run_server(port, debug)