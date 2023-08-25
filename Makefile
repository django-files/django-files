venv:
	python -m venv venv
requirements:
	pip install -r app/requirements-dev.txt
dev:
	make venv requirements
