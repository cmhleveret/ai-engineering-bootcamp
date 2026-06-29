# This is a fast api app
(this folder is a mono repo with multiple projects in it now - with the deps managed indepenadtly)

## Will need to add some deps 
in the folder use uv add (from the root folder)
```
uv add --package api fastapi google-genai groq openai pydantic pydantic-settings uvicorn
```
uvicorn is a framework to deploy backend servers

## add more deps to the pyproject.toml
to build the api we need to add
'''
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv.sources]
shared = { workspace = true }

[tool.hatch.build.targets.wheel]
packages = ["src/api"]

[tool.hatch.build.targets.sdist]
include = [
    "src/",
    "tests/",
    "README.md",
]
''' 
## Now to the app its self in app.py
what is pydantic? 
one of the ways we can define strucuture and schema for our data classes
fastapi uses pydantic data classes a lot 
fastapi scheme for req/res are defined by pydantic

pydantic data model can be defined using a class
1. import data model
```
from pydantic import BaseModel
```
2. define the expected field for this class
```
class ChatRequest(BaseModel):
    provider: str
    models_name: str
    messages: list[dict]
```
the response of the endpoint will be an aswer or message
```
class ChatResponse(BaseModel):
    message: str
```
this is a list of dictioaries - either a system or user message
3. inititalise the application class
```
app = FastAPI()
```
4.use this app as a decorator for the function which will be invoked when placing a request to a specific endpint 
```
@app.post("/chat")
def chat(
    request: Request,
    payload: ChatRequest
) -> ChatResponse:

    result = run_llm(payload.provider, payload.models_name, payload.messages)

    return ChatResponse(message=result)

    result = run_llm(payload.provider)
```
if a post request is sent to a chat path in our endpoint
then this fucntion (below) decorated with the decorator will be triggered
and respond with the outpus of the function within (look at app.py)

(typed the function expects ChatResponse)

returns a pydantic model with a message in it
4.
We can run this app uisng docker compose
we will store app specific docker file in the root of each app
```
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Copy workspace root files for dependency resolution
COPY pyproject.toml uv.lock ./

# Copy package files and source
COPY apps/api ./apps/api

ENV UV_COMPILE_BYTECODE=1

# Install dependencies including workspace packages
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package api

# Enable bytecode compilation and Python optimization
ENV PYTHONOPTIMIZE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set PATH to use the virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/apps/api/src:$PYTHONPATH"

# Create non-root user and set permissions
RUN addgroup --system app && \
    adduser --system --ingroup app app && \
    chown -R app:app /app

# Switch to non-root user
USER app

# Expose the FastAPI port
EXPOSE 8000

WORKDIR /app/apps/api/src

# Command to run the application
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```
compared to the first app we need BOTH pyproject.tomls (or all) within this toml so all apps build correctly

FastApi usually exposed at 8000

change the working dir 
WORKDIR /app/apps/api/src
0.0.0.0 = any ip 
--reload = usually wouldnt have this as it looks for file changes (so not used in prod just for dev)
5. So now we change the dockercompose yaml in the root of the monorepo
by adding an additional service 
```
  api:
    build:
      context: .
      dockerfile: apps/api/Dockerfile
    ports:
      - 8000:8000
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - ./apps/api/src:/app/apps/api/src
```
here we mount the src directory 
'''
 - ./apps/api/src:/app/apps/api/src
 '''
inside the docker container 
so any changes in the folder propogate and are taken in to account 
6. lets take a look 
http://localhost:8000/docs
here we can see all the endpoints paths and whats expected by each 
we can also test it here 
so we dont need a front end to test the backend
i.e
```
{
  "provider": "Google",
  "models_name": "gemini-2.5-flash",
  "messages": [
    {
      "role": "user", "content": "hello"
    }
  ]
}
```
So this is transformed into the pydantic model from previously
```
class ChatRequest(BaseModel):
    provider: str
    models_name: str
    messages: list[dict]
```
returning 
```
{
  "message": "Hello! How can I help you today?"
}
```
here
```
class ChatResponse(BaseModel):
    message: str
```
So here we have a local fastapi server
