# faat.cue - A simple messaging client to coordinate tasks


## Background

I created this project to help coordinate tasks on different computers.

It'd be nice if a task finishing on one computer could cue a task to run on a different computer.
For example, a workstation can securely notify a user when something interesting happens on a server.

```cmd
python -m pip install faat.cue
```

Here are some examples of what you can do with the client.

```cmd
cue auth

cue wait smarty-pants-32 && echo I got your message

sleep 4 && cue post smarty-pants-32

cue on smarty-pants-32 echo I got your message
```
