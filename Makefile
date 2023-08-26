venv:
	python -m venv venv
requirements:
	pip install -r app/requirements.txt
dev:
	make venv requirements
