#!/bin/bash

# Wait database initialization and apply migrations if needed
sleep 3
alembic upgrade head

# Init subscriber process
python app/mqtt/subscriber.py &
