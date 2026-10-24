# Deploy on Windows WSL2 or Ubuntu Linux

Prerequisites: Ubuntu 22.04+/24.04, network access to GitHub and Python package repositories, a few GB of disk, uv installed from https://docs.astral.sh/uv/getting-started/installation/ .

Windows first runs wsl --install -d Ubuntu, then opens the Ubuntu terminal.
Keep the runtime in Linux home storage, e.g. ~/develop/gongzhi-teamspace, NOT /mnt/c.

    git clone https://github.com/luoyif/gongzhi-teamspace.git
    cd gongzhi-teamspace
    bash app/deployment/install.sh
    .venv/bin/python app/deployment/service.py start
    .venv/bin/python app/deployment/service.py status

Visit http://127.0.0.1:47821 and set the initial admin account.

Data is in ./data by default, never in Git. The backup command archives both SQLite and private credentials and must be stored confidentially.

    .venv/bin/python app/deployment/backup.py
    .venv/bin/python app/deployment/service.py stop
    .venv/bin/python app/deployment/service.py start

Restore into an empty staging directory first with app/deployment/restore_check.py; do not overwrite a live instance.

For Internet access use an HTTPS reverse proxy. Preserve SSE streaming (proxy buffering off), set login limits and timeout controls; do not expose SQLite or ssh secrets to Internet.
