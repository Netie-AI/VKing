.PHONY: run doctor clean install

PYTHON ?= python
VENV ?= .venv
PORT ?= 8765

install:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/Scripts/pip install -r requirements.txt

run:
	$(PYTHON) -m uvicorn vking_proto.app:app --host 127.0.0.1 --port $(PORT)

doctor:
	$(PYTHON) -c "from vking_proto import doctor; import json; print(json.dumps(doctor.doctor_report(), indent=2))"

clean:
	rm -rf runs/*
	rm -rf __pycache__ vking_proto/__pycache__
