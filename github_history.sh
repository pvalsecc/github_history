#!/usr/bin/env bash
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [[ ! -d .venv ]]
then
    /usr/bin/virtualenv --python=/usr/bin/python3 ${DIR}/.venv
    ${DIR}/.venv/bin/pip install -r requirements.txt
fi

export PYTHONPATH=${DIR}:$PYTHONPATH
${DIR}/.venv/bin/python ${DIR}/github_history/main.py "$@"
