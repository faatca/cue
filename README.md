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
cue auth https://your-server-name-here

cue wait smarty-pants-32 && echo I got your message

sleep 4 && cue post smarty-pants-32

cue on smarty-pants-32 echo I got your message
```


## API

Here's an example of using cues in python code.

```python
import faat.cue

with faat.cue.connect() as client:
    client.post("heyo")
    for c in client.listen("heyo"):
        print("got cue", c)
```

There's also an async version of the client.

```python
import asyncio
import faat.cue


async def go():
    async with faat.cue.connect_async() as client:
        await client.post("heyo")
        async for c in client.listen("heyo"):
            print("got cue", c)
            break


asyncio.run(go())
```
