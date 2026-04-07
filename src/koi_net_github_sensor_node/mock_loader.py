#!/usr/bin/env python3
"""
Mock data loader for GitHub Sensor Node.

Loads JSON files and processes them by pushing bundles to the queue.
"""

import json
import re
from pathlib import Path

import structlog
from rid_lib.ext import Bundle
from rid_lib.types import GithubRepo


log = structlog.stdlib.get_logger()


class GithubMockLoader:
    """Loads mock GitHub repo data by processing JSON files."""
    
    def __init__(
        self,
        mock_data_path: str,
        kobj_queue,
        log=None,
    ):
        self.mock_data_path = Path(mock_data_path)
        self.kobj_queue = kobj_queue
        self.log = log or structlog.stdlib.get_logger()
    
    def _extract_repo_from_orn(self, orn: str) -> tuple:
        match = re.match(r"orn:github\.repo:([^/]+)/(.+)", orn)
        if match:
            return match.group(1), match.group(2)
        raise ValueError(f"Invalid GitHub ORN: {orn}")
    
    def load_all(self):
        """Load all mock JSON files and process them."""
        if not self.mock_data_path.exists():
            self.log.warning(f"Mock data path does not exist: {self.mock_data_path}")
            return 0
        
        loaded = 0
        for filepath in self.mock_data_path.glob("*.json"):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                
                contents = data.get("contents", {})
                manifest_rid = data.get("manifest", {}).get("rid", "")
                
                owner, repo = self._extract_repo_from_orn(manifest_rid)
                repo_rid = GithubRepo(owner, repo)
                
                bundle = Bundle.generate(rid=repo_rid, contents=contents)
                self.kobj_queue.push(bundle=bundle)
                self.log.debug(f"Queued mock GitHub repo: {repo_rid}")
                loaded += 1
                
            except Exception as e:
                self.log.error(f"Failed to load {filepath.name}: {e}")
        
        self.log.info(f"Loaded {loaded} mock GitHub repos")
        return loaded
