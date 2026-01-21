-- Recreate the table with clean columns
DROP TABLE IF EXISTS public.defects CASCADE;

CREATE TABLE public.defects (
    id SERIAL PRIMARY KEY,
    defect_title TEXT NOT NULL,
    module TEXT NOT NULL,
    priority TEXT NOT NULL,
    reported_by TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'New',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
