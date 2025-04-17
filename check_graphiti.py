#!/usr/bin/env python
"""
Script to check the method signature of Graphiti.add_episode
"""

import inspect
from graphiti_core import Graphiti

# Create a dummy instance
g = Graphiti("bolt://localhost:7687", "neo4j", "password")

# Get the signature of the add_episode method
sig = inspect.signature(g.add_episode)
print(f"Signature of Graphiti.add_episode: {sig}")

# Get the documentation
print("\nDocumentation:")
print(g.add_episode.__doc__) 