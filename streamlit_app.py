-- 1. Setup the final table structure
DROP TABLE IF EXISTS public.defects CASCADE;

CREATE TABLE public.defects (
    id SERIAL PRIMARY KEY,
    defect_title TEXT NOT NULL,
    module TEXT NOT NULL,
    priority TEXT NOT NULL,
    category TEXT DEFAULT 'Functional',
    environment TEXT DEFAULT 'Production',
    status TEXT NOT NULL DEFAULT 'New',
    reported_by TEXT NOT NULL,
    reporter_email TEXT NOT NULL,
    assigned_to TEXT DEFAULT 'Unassigned',
    description TEXT,
    comments TEXT,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- 2. Setup the history log
CREATE TABLE IF NOT EXISTS public.defect_history (
    id SERIAL PRIMARY KEY,
    defect_id INTEGER REFERENCES public.defects(id) ON DELETE CASCADE,
    old_status TEXT,
    new_status TEXT,
    changed_by TEXT,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
