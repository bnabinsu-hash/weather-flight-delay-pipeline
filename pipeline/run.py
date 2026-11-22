"""
Run the full pipeline:  extract -> transform -> quality checks -> load

    python -m pipeline.run
"""
import logging
import time

from pipeline import extract, load, quality, transform

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-5s  %(name)-18s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


def main() -> None:
    start = time.perf_counter()
    steps = [
        ("extract", extract.run),
        ("transform", transform.run),
        ("quality", quality.run),
        ("load", load.run),
    ]
    for name, step in steps:
        t0 = time.perf_counter()
        log.info("=== %s ===", name.upper())
        step()
        log.info("%s finished in %.1fs", name, time.perf_counter() - t0)
    log.info("pipeline complete in %.1fs -> data/warehouse.duckdb", time.perf_counter() - start)


if __name__ == "__main__":
    main()
