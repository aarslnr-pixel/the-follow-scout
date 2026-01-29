# Apify Actor - The Follow Scout
# Python 3.11 base image with Apify SDK
FROM apify/actor-python:3.11

# Copy requirements and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY main.py ./

# Run the actor
CMD ["python", "-u", "main.py"]
