-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.business_profiles (
  profile_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL,
  business_name character varying NOT NULL,
  business_type character varying NOT NULL,
  location character varying NOT NULL,
  district character varying,
  unique_selling_points text,
  data_source character varying NOT NULL DEFAULT 'manual'::character varying,
  years_operating integer CHECK (years_operating >= 0 AND years_operating <= 200),
  price_range_min double precision CHECK (price_range_min >= 0::double precision),
  price_range_max double precision,
  created_at timestamp without time zone DEFAULT now(),
  updated_at timestamp without time zone DEFAULT now(),
  customer_type character varying DEFAULT 'B2C'::character varying,
  b2b_business_sizes ARRAY,
  b2b_avg_transaction_rm double precision,
  b2b_purchase_frequency character varying,
  b2b_decision_factors ARRAY,
  b2c_target_segments ARRAY,
  b2b_target_types ARRAY,
  CONSTRAINT business_profiles_pkey PRIMARY KEY (profile_id),
  -- user_id references auth.users (Supabase Auth) — NOT public.users
  CONSTRAINT business_profiles_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE
);

CREATE TABLE public.chat_messages (
  message_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  session_id uuid NOT NULL,
  role character varying NOT NULL CHECK (role::text = ANY (ARRAY['user'::character varying, 'aria'::character varying]::text[])),
  content text NOT NULL,
  message_metadata jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT chat_messages_pkey PRIMARY KEY (message_id),
  CONSTRAINT chat_messages_session_fk FOREIGN KEY (session_id) REFERENCES public.chat_sessions(session_id)
);

CREATE TABLE public.chat_sessions (
  session_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  user_id uuid NOT NULL,
  profile_id uuid,
  started_at timestamp with time zone DEFAULT now(),
  last_message_at timestamp with time zone DEFAULT now(),
  CONSTRAINT chat_sessions_pkey PRIMARY KEY (session_id),
  -- user_id references auth.users (Supabase Auth) — NOT public.users
  CONSTRAINT chat_sessions_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE,
  CONSTRAINT chat_sessions_profile_fk FOREIGN KEY (profile_id) REFERENCES public.business_profiles(profile_id)
);

CREATE TABLE public.scenarios (
  scenario_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  profile_id uuid NOT NULL,
  scenario_name character varying NOT NULL,
  scenario_type character varying NOT NULL,
  description text NOT NULL,
  parameters jsonb NOT NULL,
  created_at timestamp without time zone DEFAULT now(),
  CONSTRAINT scenarios_pkey PRIMARY KEY (scenario_id),
  CONSTRAINT scenarios_profile_fk FOREIGN KEY (profile_id) REFERENCES public.business_profiles(profile_id)
);

CREATE TABLE public.simulation_events (
  event_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  simulation_id uuid NOT NULL,
  agent_id integer NOT NULL,
  income_level character varying NOT NULL,
  decision character varying NOT NULL CHECK (decision::text = ANY (ARRAY['visit'::character varying, 'skip'::character varying, 'churn'::character varying]::text[])),
  reasoning text NOT NULL,
  spend_amount double precision NOT NULL DEFAULT 0,
  profile_text text,
  recorded_at timestamp without time zone DEFAULT now(),
  CONSTRAINT simulation_events_pkey PRIMARY KEY (event_id),
  CONSTRAINT events_simulation_fk FOREIGN KEY (simulation_id) REFERENCES public.simulations(simulation_id)
);

CREATE TABLE public.simulation_reports (
  report_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  simulation_id uuid NOT NULL UNIQUE,
  risk_level character varying NOT NULL CHECK (risk_level::text = ANY (ARRAY['Low'::character varying, 'Medium'::character varying, 'High'::character varying]::text[])),
  churn_rate double precision NOT NULL,
  visit_rate double precision NOT NULL,
  estimated_revenue double precision NOT NULL,
  archetype_breakdown jsonb NOT NULL,
  recommendations jsonb NOT NULL,
  analysis text,
  key_reasons jsonb DEFAULT NULL,
  monte_carlo_summary jsonb DEFAULT NULL,
  created_at timestamp without time zone DEFAULT now(),
  CONSTRAINT simulation_reports_pkey PRIMARY KEY (report_id),
  CONSTRAINT reports_simulation_fk FOREIGN KEY (simulation_id) REFERENCES public.simulations(simulation_id)
);

CREATE TABLE public.simulations (
  simulation_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  scenario_id uuid NOT NULL,
  status character varying NOT NULL CHECK (status::text = ANY (ARRAY['pending'::character varying, 'running'::character varying, 'completed'::character varying, 'failed'::character varying, 'paused'::character varying]::text[])),
  current_week integer DEFAULT 0,
  agent_count integer NOT NULL,
  progress_percentage double precision DEFAULT 0.0,
  monte_carlo_enabled boolean DEFAULT false,
  monte_carlo_total_runs integer DEFAULT 1,
  monte_carlo_converged boolean DEFAULT NULL,
  started_at timestamp without time zone,
  completed_at timestamp without time zone,
  error_message text,
  created_at timestamp without time zone DEFAULT now(),
  CONSTRAINT simulations_pkey PRIMARY KEY (simulation_id),
  CONSTRAINT simulations_scenario_fk FOREIGN KEY (scenario_id) REFERENCES public.scenarios(scenario_id)
);

-- NOTE: public.users and public.password_reset_tokens have been removed.
-- User identity is now managed entirely by Supabase Auth (auth.users).
-- See migrations/002_supabase_auth_migration.sql for the transition SQL.

-- Index for filtering Monte Carlo simulations
CREATE INDEX simulations_monte_carlo_idx ON public.simulations(monte_carlo_enabled, monte_carlo_converged);

CREATE TABLE public.sales_records (
  record_id uuid NOT NULL DEFAULT uuid_generate_v4(),
  profile_id uuid NOT NULL,
  sale_date date NOT NULL,
  total_sales double precision NOT NULL CHECK (total_sales >= 0),
  transaction_count integer DEFAULT NULL CHECK (transaction_count >= 0),
  source varchar(50) NOT NULL DEFAULT 'manual'
    CHECK (source IN ('manual')),
  notes text DEFAULT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT sales_records_pkey PRIMARY KEY (record_id),
  CONSTRAINT sales_records_profile_fk FOREIGN KEY (profile_id) REFERENCES public.business_profiles(profile_id) ON DELETE CASCADE
);

-- Index for efficient date-range queries
CREATE INDEX sales_records_profile_date_idx ON public.sales_records (profile_id, sale_date DESC);

-- Prevent duplicate entries for same business + same date
CREATE UNIQUE INDEX sales_records_unique_day_idx ON public.sales_records (profile_id, sale_date);