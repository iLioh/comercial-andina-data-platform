.PHONY: install quality test generate validate-bicep

install:
	python -m pip install -e ".[dev]"

quality:
	ruff check .

test:
	pytest

generate:
	comercial-andina generate

validate-bicep:
	az bicep build --file infra/bicep/main.bicep --stdout > /dev/null
