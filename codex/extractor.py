from __future__ import annotations

import logging
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from codex.run_codex import run_codex

PROMPT = "[input.md](input/input.md) 开始extract"


@dataclass(frozen=True)
class Agent:
    name: str
    directory: Path

    @property
    def input_file(self) -> Path:
        return self.directory / "input" / "input.md"


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    codex_root = repo_root / "codex" / "extractor"
    agents = [
        Agent(name=name, directory=codex_root / name)
        for name in ("background", "concept", "formula")
    ]

    if not codex_root.is_dir():
        logging.error("codex/extractor directory not found: %s", codex_root)
        return 1

    missing_dirs = [agent for agent in agents if not agent.directory.is_dir()]
    if missing_dirs:
        for agent in missing_dirs:
            logging.error("Agent directory not found for %s: %s", agent.name, agent.directory)
        return 1

    missing_inputs = [agent for agent in agents if not agent.input_file.is_file()]
    if missing_inputs:
        for agent in missing_inputs:
            logging.error("Input file not found for %s: %s", agent.name, agent.input_file)
        return 1

    logging.info("Launching %d extractor agent(s) concurrently.", len(agents))
    exit_code = 0
    with ThreadPoolExecutor(max_workers=len(agents)) as executor:
        futures = {
            executor.submit(
                run_codex,
                PROMPT,
                agent.directory,
                model="gpt-5.2",
                model_reasoning_effort="high",
                new_console=True,
            ): agent
            for agent in agents
        }

        for future in as_completed(futures):
            agent = futures[future]
            try:
                future.result()
            except FileNotFoundError:
                logging.error("`codex` command not found. Ensure it is installed and on PATH.")
                exit_code = exit_code or 1
            except subprocess.CalledProcessError as exc:
                logging.error("codex exited with code %s for %s", exc.returncode, agent.name)
                exit_code = exit_code or exc.returncode
            except Exception:
                logging.exception("Unhandled error for %s", agent.name)
                exit_code = exit_code or 1
            else:
                logging.info("Extractor agent %s completed.", agent.name)

    if exit_code == 0:
        logging.info("Extractor processing completed.")
    return exit_code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
