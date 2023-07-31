venv:
	pyenv virtualenv 3.11 venv

requirements:
	pip install -r requirements.txt

dev:
	make venv requirements
