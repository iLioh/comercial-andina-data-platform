.PHONY: install quality test generate validate-cfn

install:
	python -m pip install -e ".[dev]"

quality:
	ruff check .

test:
	pytest

generate:
	comercial-andina generate

validate-cfn:
	cfn-lint infra/cloudformation/*.yml
