import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from energy import app
from energy.views import *

test_site = app.test_client()