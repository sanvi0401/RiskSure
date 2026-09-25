import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import app as flask_app

class ApiPrefixMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        if path == "/api":
            environ["PATH_INFO"] = "/"
        elif path.startswith("/api/"):
            environ["PATH_INFO"] = path[4:]
        return self.wsgi_app(environ, start_response)

flask_app.wsgi_app = ApiPrefixMiddleware(flask_app.wsgi_app)
app = flask_app
