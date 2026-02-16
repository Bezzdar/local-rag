.PHONY: verify run-api smoke

verify:
	bash scripts/verify.sh

run-api:
	bash scripts/dev_run.sh

smoke:
	bash scripts/verify.sh
