# cue - A simple messaging service for coordinating tasks


## Background

I created this project to help coordinate tasks on different computers.

It'd be nice if a task finishing on one computer could cue a task to run on a different computer.
For example, a workstation can notify a user when something interesting happens on a server.


## Running a local server

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
python -m pip install yarl websockets
```

Here are some examples of what you can do with the client.

```cmd
cue auth

cue wait smarty-pants-32 && echo I got your message

sleep 4 && cue post smarty-pants-32

cue on smarty-pants-32 echo I got your message
```


## Installing on server

We need a current version of python.
Let's install 3.10.

```bash
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.10
sudo apt install python3.10-venv
```

```bash
cd /var/www
sudo mkdir cue
sudo chown deploy:deploy cue
cd cue
```

```bash
python3.10 -m venv venv
venv/bin/python -m pip install -U pip
venv/bin/python -m pip install wheel
venv/bin/pip install starlette uvicorn[standard]
venv/bin/python -m pip install faat.userdb

nano cueserver.py
venv/bin/userdb add-user users.db aaron secret

export CUE_USER_DB=users.db
venv/bin/uvicorn --port 4007 cueserver:app
```

```bash
sudo chown -R root:root /var/www/cue
sudo chown www-data:www-data /var/www/cue/users.db
```

```bash
sudo nano /etc/systemd/system/cueserver.service
```

```bash
[Unit]
Description=Rident API
After=network.target

[Service]
User=www-data
Group=www-data
ExecStart=/var/www/cue/venv/bin/uvicorn \
    --port 4007 \
    --no-server-header \
    cueserver:app
WorkingDirectory=/var/www/cue
Environment=CUE_USER_DB=/var/www/cue/users.db
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start cueserver
```


### Set up NGINX

```bash
sudo nano /etc/nginx/snippets/letsencrypt.conf
```

```bash
location ^~ /.well-known/acme-challenge/ {
    default_type "text/plain";
    root /var/www/letsencrypt;
}
```

```bash
sudo nano /etc/nginx/sites-available/cue.faat.ca.conf
```

```nginx
server {
    listen 80;
    server_name cue.faat.ca;

    include /etc/nginx/snippets/letsencrypt.conf;
}
```

```bash
sudo ln -s /etc/nginx/sites-available/cue.faat.ca.conf /etc/nginx/sites-enabled/cue.faat.ca.conf
sudo systemctl reload nginx
sudo certbot certonly --webroot
sudo nano /etc/nginx/sites-available/cue.faat.ca.conf
```

```bash
server {
    listen 80;
    server_name cue.faat.ca;

    include /etc/nginx/snippets/letsencrypt.conf;

    location / {
        return 301 https://cue.faat.ca$request_uri;
    }
}

server {
    server_name cue.faat.ca;
    listen 443 ssl http2;

    ssl_certificate /etc/letsencrypt/live/cue.faat.ca/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cue.faat.ca/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/cue.faat.ca/fullchain.pem;
    include /etc/nginx/snippets/ssl.conf;

    location / {
        proxy_pass http://127.0.0.1:4007/;
        proxy_redirect off;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_buffering off;
    }
}
```

```bash
sudo nano /etc/nginx/conf.d/websockets.conf
```

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}
```

```bash
sudo systemctl reload nginx
```
