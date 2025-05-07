# Dockerfile
# Use the same Python version you developed with (e.g., 3.9)
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt ./requirements.txt

# Install dependencies using pip (uv isn't standard in base images)
# --no-cache-dir keeps the image slightly smaller
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code into the container's working directory
COPY . .

# Expose the port Streamlit typically runs on
EXPOSE 8501

# Add healthcheck for the platform to monitor the app status
# Uses the $PORT variable which Render provides, defaults to 8501 otherwise
HEALTHCHECK CMD streamlit hello --server.port=${PORT:-8501}

# Command to run when the container starts
# Tells Streamlit to run on all available network interfaces (0.0.0.0)
# and use the port provided by the platform ($PORT) or default to 8501
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=${PORT:-8501}", "--server.address=0.0.0.0"]