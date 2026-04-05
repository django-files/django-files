venv:
	uv venv venv
requirements:
	uv pip install -r app/requirements.txt
dev:
	make venv requirements
