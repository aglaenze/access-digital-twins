"""The class password of the online version (start.sh web): the login page of Jupyter Server ("Password or token",
"Token authentication is enabled"...) replaced by a page of the twins that asks for the class password. The password
is the token of Voila (TWIN_WEB_PASSWORD); the form posts the same fields to the same address.

    voila ... --token=<password> --Voila.identity_provider_class=web_login.ClassPassword
"""
import os

import jinja2
from jupyter_server.auth.identity import PasswordIdentityProvider
from voila.voila_identity_provider import VoilaLoginHandler

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_data", "voila", "templates", "twin")
_env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATES), autoescape=True)


class ClassLoginHandler(VoilaLoginHandler):
    def _render(self, message=None):
        self.write(_env.get_template("login.html").render(
            base_url=self.base_url, next=self.get_argument("next", default=self.base_url),
            message=message, xsrf_form_html=self.xsrf_form_html))


class ClassPassword(PasswordIdentityProvider):
    def __init__(self, **kw):           # (Voila passes its own login_handler_class: replaced)
        kw["login_handler_class"] = ClassLoginHandler
        super().__init__(**kw)
