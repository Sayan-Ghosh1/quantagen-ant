-- =========================================================================
-- QuantGen: Supabase Schema Migration for Live Investment Tracking & Alerts
-- =========================================================================

-- 1. Ensure portfolio_holdings table exists (Existing table used by Tracker)
CREATE TABLE IF NOT EXISTS public.portfolio_holdings (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    symbol VARCHAR(30) NOT NULL,
    purchase_date DATE NOT NULL,
    purchase_time VARCHAR(10) NOT NULL,
    invested_amount NUMERIC(15, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. Create portfolio_notifications table for Model 2 live strategy alerts
CREATE TABLE IF NOT EXISTS public.portfolio_notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    symbol VARCHAR(30) NOT NULL,
    action VARCHAR(20) NOT NULL, -- 'BUY', 'HOLD', 'SELL'
    action_type VARCHAR(50),     -- 'TAKE_PROFIT', 'STOP_LOSS', 'MOMENTUM_BUY', 'TREND_HOLD'
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    current_price NUMERIC(12, 2),
    pnl_percent NUMERIC(8, 2),
    target_price NUMERIC(12, 2),
    stop_loss_price NUMERIC(12, 2),
    confidence NUMERIC(5, 2),
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Enable Row-Level Security (RLS) for data privacy
ALTER TABLE public.portfolio_holdings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_notifications ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policies: Allow users to view and insert only their own records
DROP POLICY IF EXISTS "Users can manage own holdings" ON public.portfolio_holdings;
CREATE POLICY "Users can manage own holdings"
    ON public.portfolio_holdings
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view own notifications" ON public.portfolio_notifications;
CREATE POLICY "Users can view own notifications"
    ON public.portfolio_notifications
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- 5. Enable Realtime publication for live notifications
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables 
        WHERE pubname = 'supabase_realtime' AND tablename = 'portfolio_notifications'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE public.portfolio_notifications;
    END IF;
END $$;
