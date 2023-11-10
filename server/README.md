# faat.cueserver - A simple messaging service for coordinating tasks


## Background

I created this project to help coordinate tasks on different computers.

It'd be nice if a task finishing on one computer could cue a task to run on a different computer.
For example, a workstation can notify a user when something interesting happens on a server.


## Running a local server for development

Here's how you can run a development server.

Generate a random session key.

```bash
openssl rand -hex 32
```

Set up a .env file.

```text
DEBUG=True

OAUTH_CLIENT_ID=--your-values-from-auth0-here--
OAUTH_CLIENT_SECRET=--your-values-from-auth0-here--
OAUTH_DOMAIN=--your-values-from-auth0-here--

SESSION_SECRET_KEY=--your-session-key-here--
SESSION_HTTPS_ONLY=False

CUE_REDIS_URL=redis://localhost
```

Set up the virtual environment.

```bash
cd server
python3.11 -m venv venv
venv/bin/python -m pip install -U pip wheel
venv/bin/python -m pip install -e .
venv/bin/python -m pip install uvicorn[standard]
```

And run it.

```bash
venv/bin/uvicorn faat.cueserver.web:app --reload --port 8002
```


## Installing on server

Installing for production use is more involved.
