.PHONY: install dev api obis-mcp route-mcp build up down logs test lint clean

# ─────────────────────────────────────────────────────────────────
# Local development
# ─────────────────────────────────────────────────────────────────

install:
	pip install -r requirements.txt

dev: install
	cp -n .env.example .env || true
	@echo "Edit .env and add your GROQ_API_KEY, then run: make api"

# Start the FastAPI server directly (no Docker)
api:
	python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Start MCP servers (separate terminals)
obis-mcp:
	python -m mcp_servers.obis_server

route-mcp:
	python -m mcp_servers.route_calc_server

# CLI interactive menu
cli:
	python main.py

# ─────────────────────────────────────────────────────────────────
# Docker
# ─────────────────────────────────────────────────────────────────

build:
	docker build -t cetacean-router:latest .

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api

# ─────────────────────────────────────────────────────────────────
# Quality
# ─────────────────────────────────────────────────────────────────

lint:
	python -m py_compile config/settings.py agents/*.py graph/*.py \
		mcp_servers/*.py api/*.py utils/*.py rp_handler.py main.py
	@echo "Syntax OK"

test-obis:
	python -c "from pyobis import occurrences; print('OBIS OK')"

test-imports:
	python -c "import groq, langgraph, fastmcp, shapely, pyobis; print('All imports OK')"

# ─────────────────────────────────────────────────────────────────
# RunPod
# ─────────────────────────────────────────────────────────────────

runpod:
	python rp_handler.py

# ─────────────────────────────────────────────────────────────────
# Cleanup
# ─────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true