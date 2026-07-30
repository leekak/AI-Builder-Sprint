.PHONY: install run test seed clean

install:
	python -m pip install -r requirements.txt

run:
	python run.py

test:
	pytest

seed:
	python scripts/seed.py

clean:
	rm -f data/memory_recall.db
	find data/uploads -type f ! -name '.gitkeep' -delete
