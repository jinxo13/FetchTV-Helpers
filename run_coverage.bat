coverage run --omit */venv/* --omit */tests/* -m unittest discover
coverage xml
coverage html
