# Common tasks. Run `make setup` once, then `make backend` and `make frontend` in two terminals.
PY := .venv/bin/python
.PHONY: setup backend frontend test test-slow build e2e seed lint-template deploy deploy-frontend zip clean

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r backend/requirements-dev.txt
	cd frontend && npm install

backend:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && ../.venv/bin/pytest -q
	cd frontend && npm test

test-slow:
	cd backend && ../.venv/bin/pytest -q -m slow

build:
	cd frontend && npm run build

e2e:
	$(PY) scripts/e2e_demo.py --base http://localhost:8000

lint-template:
	.venv/bin/cfn-lint infrastructure/template.yaml

deploy:
	cd infrastructure && sam build && sam deploy

deploy-frontend:
	sh scripts/deploy_frontend.sh $(STACK) $(REGION)

seed:
	$(PY) scripts/seed_demo.py --table $(TABLE) --region $(REGION) --pool $(POOL)

zip:
	sh scripts/make_zip.sh

clean:
	rm -rf .venv frontend/node_modules frontend/dist .data infrastructure/.aws-sam backend/.pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
