-- Drop existing tables
DROP TABLE IF EXISTS trades CASCADE;

-- Create trades table
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    trade_id VARCHAR(50) UNIQUE NOT NULL,
    order_id VARCHAR(50),
    position_id VARCHAR(50),
    mt5_ticket VARCHAR(50),
    
    -- Trade details
    instrument VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DECIMAL NOT NULL,
    type VARCHAR(20) NOT NULL,
    
    -- Prices
    ask_price DECIMAL,
    bid_price DECIMAL,
    execution_price DECIMAL,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'new',
    error_message TEXT,
    is_closed BOOLEAN DEFAULT FALSE,
    
    -- JSON data
    tv_request JSONB,
    tv_response JSONB,
    execution_data JSONB,
    mt5_response JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP WITH TIME ZONE,
    
    -- Indexes
    CONSTRAINT trades_trade_id_key UNIQUE (trade_id)
);

-- Create indexes
CREATE INDEX idx_trades_order_id ON trades(order_id);
CREATE INDEX idx_trades_position_id ON trades(position_id);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_instrument ON trades(instrument);
CREATE INDEX idx_trades_created_at ON trades(created_at);