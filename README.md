# cue - A simple messaging service for coordinating tasks


## Background

I created this project to help coordinate tasks on different computers.

It'd be nice if a task finishing on one computer could cue a task to run on a different computer.
For example, a workstation can notify a user when something interesting happens on a server.


## Running a Cue server

Here's how you can run a development server.

```cmd
py -m venv venv
venv\Scripts\python -m pip install -U pip
venv\Scripts\python -m pip install wheel
venv\Scripts\python -m pip install faat.userdb
venv\Scripts\pip install starlette uvicorn[standard]

venv\Scripts\userdb.exe add-user users.db aaron secret

SET CUE_USER_DB=users.db

venv\Scripts\uvicorn cueserver:app
```


## Running a Cue client

The client requires the websockets library.

```cmd
python -m pip install websockets
```

Here are some examples of what you can do with the client.

```cmd
cue auth

cue wait smarty-pants-32 && echo I got your message

sleep 4 && cue post smarty-pants-32

cue on smarty-pants-32 echo I got your message
```
