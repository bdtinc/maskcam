#!/bin/bash

# Wait database initialization and apply migrations if needed
sleep 3
alembic upgrade head

# Init suscriber process
python app/mqtt/suscriber.py &
