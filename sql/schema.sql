
-- NHS Antidepressant Prescribing Analysis — Database Schema
-- This script creates the nhs_prescribing database and all four tables
-- using a star schema design.
-- Execution order:
--   1. Create database
--   2. Create lookup tables (dates, regions, drugs)
--   3. Create fact table last (references all three lookup tables)

-- Database

CREATE DATABASE IF NOT EXISTS nhs_prescribing;

USE nhs_prescribing;

-- dates
-- Example row:
--   date_id=1, year_month='2021-01', year=2021, month=1, month_name='January'

CREATE TABLE IF NOT EXISTS dates (
    date_id     INT          NOT NULL AUTO_INCREMENT,
    `year_month`  VARCHAR(7)   NOT NULL,
    `year`      INT          NOT NULL,
    `month`     INT          NOT NULL,
    month_name  VARCHAR(10)  NOT NULL,

    PRIMARY KEY (date_id),
    UNIQUE KEY uq_year_month (`year_month`)
);

-- regions
-- One row per NHS England region.
-- Seven regions total covering all of England.
-- Example row:
--   region_id=1, region_name='North West'

CREATE TABLE IF NOT EXISTS regions (
    region_id   INT          NOT NULL AUTO_INCREMENT,
    region_name VARCHAR(100) NOT NULL,

    PRIMARY KEY (region_id),
    UNIQUE KEY uq_region_name (region_name)
);

-- drugs
-- One row per antidepressant BNF chemical substance.
-- 32 substances in total covering BNF Chapter 4.3.
-- Example row:
--   drug_id=1, bnf_chemical_substance='Sertraline hydrochloride'

CREATE TABLE IF NOT EXISTS drugs (
    drug_id                INT          NOT NULL AUTO_INCREMENT,
    bnf_chemical_substance VARCHAR(200) NOT NULL,

    PRIMARY KEY (drug_id),
    UNIQUE KEY uq_drug_name (bnf_chemical_substance)
);


-- prescriptions
-- One row per drug per region per month — the core of the star schema.
-- Stores the measurable facts: number of items prescribed and net cost.
-- Foreign keys link to all three lookup tables.
-- The unique constraint on (date_id, region_id, drug_id) prevents the
-- Example row:
--   date_id=1, region_id=1, drug_id=1, items=45231, nic=107248.43

CREATE TABLE IF NOT EXISTS prescriptions (
    prescription_id  INT             NOT NULL AUTO_INCREMENT,
    date_id          INT             NOT NULL,
    region_id        INT             NOT NULL,
    drug_id          INT             NOT NULL,
    items            INT             NOT NULL,       -- number of items prescribed
    nic              DECIMAL(12, 2)  NOT NULL,       -- net ingredient cost in GBP

    PRIMARY KEY (prescription_id),

    FOREIGN KEY (date_id)   REFERENCES dates(date_id),
    FOREIGN KEY (region_id) REFERENCES regions(region_id),
    FOREIGN KEY (drug_id)   REFERENCES drugs(drug_id),

    -- Prevents duplicate records on re-run
    UNIQUE KEY uq_prescription (date_id, region_id, drug_id)
);

SHOW TABLES;