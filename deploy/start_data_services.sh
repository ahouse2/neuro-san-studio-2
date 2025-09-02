#!/bin/bash
set -e

# Start PostgreSQL, Qdrant and Neo4j containers
# Requires docker-compose to be installed

docker-compose up -d postgres qdrant neo4j
