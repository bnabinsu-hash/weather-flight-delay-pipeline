.PHONY: install pipeline pipeline-recent charts test dashboard fetch all clean

install:
	pip install -r requirements.txt

pipeline:
	python -m pipeline.run --dataset nyc2013

pipeline-recent:
	python -m pipeline.run --dataset nyc2024_25

charts:
	python -m analysis.make_charts --dataset nyc2013
	python -m analysis.make_charts --dataset nyc2024_25
	python -m analysis.compare_periods

test:
	python -m pytest -q

dashboard:
	streamlit run dashboard/app.py

# needs open internet access (BTS + Iowa Mesonet); normally run by GitHub Actions
fetch:
	python scripts/fetch_recent.py

all: pipeline pipeline-recent test charts

clean:
	rm -rf data/
