FROM python:3.11.4-slim

# Copy required files
WORKDIR /app
COPY ./twitch_drops_watchdog ./twitch_drops_watchdog
COPY ./requirements.txt .
COPY ./setup.py .

# Install app
RUN pip install .

ENTRYPOINT ["python", "-m", "twitch_drops_watchdog"]
