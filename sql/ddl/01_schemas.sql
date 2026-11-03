-- Medallion layers: raw = bronze, staging = silver, marts = gold. ops = pipeline bookkeeping.
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS ops;
