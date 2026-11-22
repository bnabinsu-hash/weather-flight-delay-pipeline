"""
Run the full pipeline:  extract -> transform -> quality checks -> load

    python -m pipeline.run                       # nyc2013 (default)
    python -m pipeline.run --dataset nyc2024_25  # 2024-2025 snapshot
"""
import argparse
import importlib
import logging
import os
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(name)-18s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


def main(dataset: str | None = None) -> None:
    if dataset:
        os.environ["PIPELINE_DATASET"] = dataset
    # import after the dataset is chosen, so every step uses the right paths
    from pipeline import config
    importlib.reload(config)
    from pipeline import extract, load, quality, transform
    for module in (extract, transform, quality, load):
        importlib.reload(module)

    start = time.perf_counter()
    log.info("dataset: %s (%s)", config.DATASET, config.DATASETS[config.DATASET])
    for name, step in [("extract", extract.run), ("transform", transform.run),
                       ("quality", quality.run), ("load", load.run)]:
        t0 = time.perf_counter()
        log.info("=== %s ===", name.upper())
        step()
        log.info("%s finished in %.1fs", name, time.perf_counter() - t0)
    log.info("pipeline complete in %.1fs -> %s", time.perf_counter() - start,
             config.WAREHOUSE.relative_to(config.ROOT))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=["nyc2013", "nyc2024_25"])
    main(parser.parse_args().dataset)
