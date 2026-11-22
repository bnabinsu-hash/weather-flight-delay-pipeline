.PHONY: install pipeline charts test dashboard all clean

install:
	pip install -r requirements.txt

pipeline:
	python -m pipeline.run

charts:
	python -m analysis.make_charts

test:
	python -m pytest -q

dashboard:
	streamlit run dashboard/app.py

all: pipeline test charts

clean:
	rm -rf data/
