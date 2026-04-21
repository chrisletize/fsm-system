-- FieldKit Phase 1: Core Schema - Users & Foundation Tables
-- Created: 2026-02-10
-- Purpose: Essential tables and triggers for all four databases

-- ============================================================================
-- TRIGGERS & FUNCTIONS
-- ============================================================================

-- Auto-update updated_at timestamp on all tables
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- USERS TABLE (Authentication & Authorization)
-- ============================================================================

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(200) NOT NULL,
    
    -- Role-based access control
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'manager', 'salesperson', 'technician')),
    
    -- Company access as JSON array
    -- Examples:
    --   Admin: ["getagrip", "kleanit_charlotte", "cts", "kleanit_sf"]
    --   Manager: ["cts"] 
    --   Salesperson: ["getagrip", "kleanit_charlotte", "cts", "kleanit_sf"]
    company_access JSONB NOT NULL DEFAULT '[]'::jsonb,
    
    -- Account status
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    
    -- Audit (no deleted_at for security - disable instead)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for users
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_active ON users(is_active);

-- Trigger for users
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- USER SESSIONS (Track active sessions)
-- ============================================================================

CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    
    -- Session metadata
    ip_address VARCHAR(45), -- IPv6 compatible
    user_agent TEXT,
    current_company VARCHAR(50), -- Which company user is viewing
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for sessions
CREATE INDEX idx_sessions_user ON user_sessions(user_id);
CREATE INDEX idx_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);
CREATE INDEX idx_sessions_company ON user_sessions(current_company);

-- ============================================================================
-- MANAGEMENT COMPANIES (Property Management Firms)
-- ============================================================================

CREATE TABLE management_companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    website VARCHAR(255),
    notes TEXT,
    
    -- Audit trail
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(100),
    deleted_at TIMESTAMP NULL,
    deleted_by VARCHAR(100)
);

-- Indexes for management companies
CREATE INDEX idx_management_companies_name ON management_companies(name);
CREATE INDEX idx_management_companies_deleted ON management_companies(deleted_at);
CREATE INDEX idx_management_companies_active ON management_companies(deleted_at) WHERE deleted_at IS NULL;

-- Trigger for management companies
CREATE TRIGGER update_management_companies_updated_at 
    BEFORE UPDATE ON management_companies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '✓ Core schema created successfully';
    RAISE NOTICE '  - users table (authentication)';
    RAISE NOTICE '  - user_sessions table (session management)';
    RAISE NOTICE '  - management_companies table';
    RAISE NOTICE '  - update_updated_at_column() trigger function';
END $$;
