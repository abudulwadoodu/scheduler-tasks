"""
scraper_agent
=============
Public interface: import run_agent from here.

Usage from another agent in the workflow:
    from scraper_agent import run_agent

    result = run_agent(url="https://example.com/product")
"""

from .agent import run_agent

__all__ = ["run_agent"]
