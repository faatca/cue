# cue - A simple messaging mechanism coordinating tasks


## Background

I created this project to help coordinate tasks on different computers.

It'd be nice if a task finishing on one computer could cue a task to run on a different computer.
For example, a workstation can notify a user when something interesting happens on a server.


## Things to do

*   Issues
    *   Security
        *   Can one slow connection hold up receiving cues for everyone?
        *   Throttle key requests
*   Features
    *   Handle permission errors at client more gracefully
    *   Provide async version of client
    *   Allow requesting tokens from the UI for other applications
