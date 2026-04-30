.PHONY: help docs build test-offline

MODE ?= without-patch

help:
	@echo "Available commands:"
	@echo "  make docs                                         - Generate documentation using Typer"
	@echo "  make build                                        - Build and submit Docker image to GCR"
	@echo "  make test-offline MODE=[with-patch|without-patch] - Run offline test (default MODE=without-patch)"

docs:
	typer lkr/main.py utils docs --output lkr.md

build:
	gcloud builds submit -t us-central1-docker.pkg.dev/lkr-dev-production/load-tests/lkr-load-test . 

test-offline:
	QUERY_ID="$(QUERY_ID)" MODEL="$(MODEL)" ./test_offline.sh $(MODE)