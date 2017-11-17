#!/usr/bin/env bash
set -e
DIR="$( cd "$(dirname "$(readlink -f "$0")")" && pwd )"

if [[ ! -d ${DIR}/.venv ]]
then
    /usr/bin/virtualenv --python=/usr/bin/python3 ${DIR}/.venv
    ${DIR}/.venv/bin/pip install -r ${DIR}/requirements.txt
fi

export PYTHONPATH=${DIR}:$PYTHONPATH
${DIR}/.venv/bin/python ${DIR}/github_history/main.py "$@"
