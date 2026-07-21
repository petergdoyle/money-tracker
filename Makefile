.DEFAULT_GOAL := help

.PHONY: setup dev-up dev-down dev-status docker-build docker-up docker-down clean help

VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip
STREAMLIT = $(VENV)/bin/streamlit

setup: $(VENV)/bin/activate

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	touch $(VENV)/bin/activate

dev-up: setup
	@if [ -f .streamlit.pid ]; then \
		echo "Streamlit is already running (PID: $$(cat .streamlit.pid))"; \
	else \
		nohup $(STREAMLIT) run app.py --server.port=8220 > streamlit.log 2>&1 & echo $$! > .streamlit.pid; \
		echo "Streamlit started in the background on port 8220 (PID: $$(cat .streamlit.pid)). Logs at streamlit.log"; \
	fi

dev-down:
	@if [ -f .streamlit.pid ]; then \
		echo "Stopping Streamlit (PID: $$(cat .streamlit.pid))..."; \
		kill $$(cat .streamlit.pid) || true; \
		rm -f .streamlit.pid; \
		echo "Streamlit stopped."; \
	else \
		echo "No running Streamlit process found (no .streamlit.pid)."; \
		pkill -f "streamlit run app.py" || true; \
	fi

dev-status:
	@if [ -f .streamlit.pid ]; then \
		PID=$$(cat .streamlit.pid); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "✅ Streamlit is RUNNING (PID: $$PID)"; \
			PORT=$$(lsof -Pan -p $$PID -i 2>/dev/null | grep LISTEN | awk '{print $$9}' | sed 's/.*://'); \
			[ -n "$$PORT" ] && echo "   🌐 Listening on: http://localhost:$$PORT" || echo "   🌐 Port: (not yet bound)"; \
			echo "   📋 Last 10 log lines (streamlit.log):"; \
			[ -f streamlit.log ] && tail -n 10 streamlit.log || echo "   (no log file found)"; \
		else \
			echo "⚠️  PID file exists but process $$PID is NOT running (stale PID)."; \
			echo "   Run 'make dev-down' to clean up, then 'make dev-up' to restart."; \
		fi \
	else \
		echo "⛔ Streamlit is NOT running (no .streamlit.pid found)."; \
	fi

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	rm -rf $(VENV)
	rm -f .streamlit.pid streamlit.log
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

help:
	@echo "========================================================================"
	@echo "💰 Money Tracker - Dev Tooling Shortcuts"
	@echo "========================================================================"
	@echo ""
	@echo "  ── Setup ──────────────────────────────────────────────────────────────"
	@echo "  make setup        - Set up Python virtual environment & install requirements"
	@echo ""
	@echo "  ── Local Dev (Streamlit) ──────────────────────────────────────────────"
	@echo "  make dev-up       - Launch Streamlit in the background (returns to prompt)"
	@echo "  make dev-down     - Stop the background Streamlit process"
	@echo "  make dev-status   - Show running state, PID, port, and recent log output"
	@echo ""
	@echo "  ── Docker ─────────────────────────────────────────────────────────────"
	@echo "  make docker-build - Build production-ready Docker container image"
	@echo "  make docker-up    - Run application stack via Docker Compose (detached)"
	@echo "  make docker-down  - Terminate Docker Compose application stack"
	@echo ""
	@echo "  ── Utility ────────────────────────────────────────────────────────────"
	@echo "  make clean        - Purge virtual environments, PIDs, logs, and cache folders"
	@echo "  make help         - Display this developer help screen (default)"
	@echo ""
	@echo "========================================================================"
