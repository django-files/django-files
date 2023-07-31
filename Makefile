venv:
	python -m venv venv
requirements:
	pip install -r requirements.txt
dev:
	make venv requirements
