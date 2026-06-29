# base img with ub support
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

# Enable bytecode compilation and Python optimization
ENV PYTHONOPTIMIZE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set python path to include src folder
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# copy only dependancy files for faster build
COPY pyproject.toml uv.lock ./

# Install dependencies including workspace packages
# syncs dependencies from pyproject.toml and uv.lock
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package api

# copu app code
COPY src ./src

# set path to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# create non-root user and set permissions
RUN addgroup --system app && \
    adduser --system --ingroup app app && \
    chown -R app:app /app && \
    mkdir -p /home/app && \
    chown -R app:app /home/app && \
    mkdir -p /home/app/.streamlit && \
    mkdir -p /home/app/.streamlit/data && \
    mkdir -p /home/app/.streamlit/cache && \
    chown -R app:app /home/app/.streamlit

# set home directory for the user
ENV HOME=/home/app

# switch to non-root user
USER app

# expose the streamlit port
EXPOSE 8501

# command to run the application
CMD ["uv", "run", "streamlit", "run", "src/app.py", "--server.address=0.0.0.0"]