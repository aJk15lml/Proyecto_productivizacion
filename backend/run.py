#!/usr/bin/env python
"""
Punto de entrada para desarrollo local.
Uso: python run.py
"""

import os
from app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
