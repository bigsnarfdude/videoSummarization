from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Import routes at the bottom after blueprint is defined
from . import routes