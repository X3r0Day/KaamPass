CREATE TABLE localities (
  id text PRIMARY KEY, en text NOT NULL, hi text NOT NULL, pin text NOT NULL CHECK (pin ~ '^[1-9][0-9]{5}$'),
  district text NOT NULL DEFAULT 'Alwar', state text NOT NULL DEFAULT 'Rajasthan'
);
CREATE TABLE skills (id text PRIMARY KEY, en text NOT NULL, hi text NOT NULL, aliases text NOT NULL);
CREATE TABLE profiles (
  phone text PRIMARY KEY CHECK (phone ~ '^\+[1-9][0-9]{7,14}$'), public_id text NOT NULL UNIQUE,
  role text NOT NULL CHECK (role IN ('worker','employer')),
  name text NOT NULL CHECK (length(name) BETWEEN 1 AND 80), lang text NOT NULL CHECK (lang IN ('en','hi')),
  area text NOT NULL REFERENCES localities, kinds text[] NOT NULL DEFAULT '{}',
  discoverable boolean NOT NULL DEFAULT false, discoverable_until date, created_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((role='worker' AND public_id ~ '^WKR-[1-9][0-9]{5}$') OR (role='employer' AND public_id ~ '^EMP-[1-9][0-9]{5}$')),
  CHECK (kinds <@ ARRAY['short_term','permanent']::text[])
);
CREATE TABLE identity_bindings (
  provider text NOT NULL, subject text NOT NULL, phone text NOT NULL REFERENCES profiles(phone),
  PRIMARY KEY (provider,subject), UNIQUE (provider,phone)
);
CREATE TABLE worker_skills (worker text REFERENCES profiles(public_id), skill text REFERENCES skills, PRIMARY KEY(worker,skill));
CREATE TABLE worker_work_areas (worker text REFERENCES profiles(public_id), area text REFERENCES localities, PRIMARY KEY(worker,area));
CREATE TABLE jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), employer text NOT NULL REFERENCES profiles(public_id),
  submission_key uuid NOT NULL, digest text NOT NULL, skill text NOT NULL REFERENCES skills,
  area text NOT NULL REFERENCES localities, kind text NOT NULL CHECK (kind IN ('short_term','permanent')),
  title varchar(100) NOT NULL, description varchar(1200) NOT NULL, starts date NOT NULL, ends date, deadline date NOT NULL,
  shift_time time, pay bigint NOT NULL CHECK (pay BETWEEN 1 AND 1000000000),
  unit text NOT NULL CHECK (unit IN ('day','shift','month','job')),
  state text NOT NULL DEFAULT 'open' CHECK (state IN ('open','assigned','cancelled','completed','filled')),
  created_at timestamptz NOT NULL DEFAULT now(), consent_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (employer,submission_key), CHECK (deadline <= starts),
  CHECK ((kind='permanent' AND ends IS NULL AND state <> 'completed') OR
         (kind='short_term' AND ends IS NOT NULL AND ends>=starts AND state <> 'filled'))
);
CREATE INDEX jobs_match ON jobs(skill,area,kind,created_at DESC) WHERE state='open';
CREATE INDEX jobs_owner ON jobs(employer,created_at DESC);
CREATE TABLE invitations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), job uuid NOT NULL REFERENCES jobs, worker text NOT NULL REFERENCES profiles(public_id),
  response text NOT NULL DEFAULT 'pending' CHECK (response IN ('pending','accepted','declined')),
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(job,worker)
);
CREATE TABLE interests (
  job uuid REFERENCES jobs, worker text REFERENCES profiles(public_id), consent_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(job,worker)
);
CREATE INDEX interests_worker ON interests(worker);
CREATE INDEX invitations_worker ON invitations(worker);
CREATE TABLE assignments (
  job uuid PRIMARY KEY REFERENCES jobs, worker text NOT NULL, reported_pay bigint CHECK (reported_pay BETWEEN 0 AND 1000000000),
  assigned_at timestamptz NOT NULL DEFAULT now(), FOREIGN KEY(job,worker) REFERENCES interests(job,worker)
);
CREATE TABLE rate_buckets (key text PRIMARY KEY, period bigint NOT NULL, hits integer NOT NULL);
