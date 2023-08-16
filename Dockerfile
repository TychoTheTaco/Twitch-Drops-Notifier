FROM python:3.11.4-slim

# Copy required files
WORKDIR /app
COPY ./twitch_drops_notifier ./twitch_drops_notifier
COPY ./email_templates ./email_templates
COPY ./requirements.txt .
COPY ./setup.py .

# Install dependencies
RUN pip install -r requirements.txt

# Install app
RUN pip install .

ENTRYPOINT ["python", "-m", "twitch_drops_notifier"]
