-- FieldKit Phase 1: Create Four Separate Databases
-- Created: 2026-02-10
-- Purpose: Initialize all four company databases

-- Drop databases if they exist (for clean reinstall)
DROP DATABASE IF EXISTS fieldkit_getagrip;
DROP DATABASE IF EXISTS fieldkit_kleanit_charlotte;
DROP DATABASE IF EXISTS fieldkit_cts;
DROP DATABASE IF EXISTS fieldkit_kleanit_sf;

-- Create four separate databases
CREATE DATABASE fieldkit_getagrip
    WITH 
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

CREATE DATABASE fieldkit_kleanit_charlotte
    WITH 
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

CREATE DATABASE fieldkit_cts
    WITH 
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

CREATE DATABASE fieldkit_kleanit_sf
    WITH 
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

-- Grant privileges (adjust username as needed)
GRANT ALL PRIVILEGES ON DATABASE fieldkit_getagrip TO postgres;
GRANT ALL PRIVILEGES ON DATABASE fieldkit_kleanit_charlotte TO postgres;
GRANT ALL PRIVILEGES ON DATABASE fieldkit_cts TO postgres;
GRANT ALL PRIVILEGES ON DATABASE fieldkit_kleanit_sf TO postgres;

\echo 'Successfully created four FieldKit databases:'
\echo '  - fieldkit_getagrip'
\echo '  - fieldkit_kleanit_charlotte'
\echo '  - fieldkit_cts'
\echo '  - fieldkit_kleanit_sf'
