-- Initial schema for TR Automation Scripts
-- Product mappings, order tracking, and customer matching

-- Product mappings: Squarespace products to QuickBooks items
CREATE TABLE IF NOT EXISTS product_mappings (
    id SERIAL PRIMARY KEY,
    internal_sku VARCHAR(100),
    squarespace_product VARCHAR(500),
    squarespace_variant VARCHAR(500),
    squarespace_sku VARCHAR(50),
    quickbooks_item VARCHAR(500),
    tannage VARCHAR(100),
    color VARCHAR(100),
    weight VARCHAR(50),
    product_type VARCHAR(50),
    needs_qb_item BOOLEAN DEFAULT FALSE,
    needs_review BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for common lookups
CREATE INDEX IF NOT EXISTS idx_product_mappings_product
    ON product_mappings(squarespace_product);
CREATE INDEX IF NOT EXISTS idx_product_mappings_needs_qb
    ON product_mappings(needs_qb_item) WHERE needs_qb_item = TRUE;
CREATE INDEX IF NOT EXISTS idx_product_mappings_needs_review
    ON product_mappings(needs_review) WHERE needs_review = TRUE;

-- QB Items reference table
CREATE TABLE IF NOT EXISTS qb_items (
    id SERIAL PRIMARY KEY,
    item_name VARCHAR(500) UNIQUE,
    item_type VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Order import tracking (prevents duplicate imports)
CREATE TABLE IF NOT EXISTS order_imports (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(50) UNIQUE,
    order_date DATE,
    customer_email VARCHAR(255),
    customer_name VARCHAR(255),
    total_amount DECIMAL(10,2),
    iif_file VARCHAR(255),
    imported_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_order_imports_date
    ON order_imports(order_date);

-- Customer matching log (analytics)
CREATE TABLE IF NOT EXISTS customer_matches (
    id SERIAL PRIMARY KEY,
    squarespace_email VARCHAR(255),
    squarespace_name VARCHAR(255),
    qb_customer_name VARCHAR(255),
    match_type VARCHAR(50),  -- email, phone, name, new
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_customer_matches_type
    ON customer_matches(match_type);
