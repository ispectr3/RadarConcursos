#!/bin/bash
set -e

# Inicia o dashboard web em segundo plano
python dashboard.py &

# Inicia o bot (scraper + notificações) em primeiro plano
exec python main.py
