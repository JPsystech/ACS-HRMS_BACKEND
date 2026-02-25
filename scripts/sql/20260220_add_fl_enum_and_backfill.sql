-- Add FL to Postgres enum for leave types (safe if it already exists)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM pg_type t
    JOIN pg_enum e ON t.oid = e.enumtypid
    WHERE t.typname = 'leave_type'
  ) THEN
    BEGIN
      ALTER TYPE leave_type ADD VALUE IF NOT EXISTS 'FL';
    EXCEPTION
      WHEN duplicate_object THEN NULL;
    END;
  END IF;
END$$;

-- Ensure leave_balances has a row for FL for current year
INSERT INTO leave_balances (employee_id, year, leave_type, opening, accrued, used, remaining, carry_forward)
SELECT e.id,
       EXTRACT(YEAR FROM CURRENT_DATE)::int,
       'FL',
       0, 0, 0, 0, 0
FROM employees e
WHERE NOT EXISTS (
  SELECT 1 FROM leave_balances b
  WHERE b.employee_id = e.id
    AND b.year = EXTRACT(YEAR FROM CURRENT_DATE)::int
    AND b.leave_type = 'FL'
);

-- Optional: retrofit prior-year FL rows if needed
-- INSERT INTO leave_balances (employee_id, year, leave_type, opening, accrued, used, remaining, carry_forward)
-- SELECT e.id, y.y, 'FL', 0, 0, 0, 0, 0
-- FROM employees e
-- CROSS JOIN (SELECT generate_series(EXTRACT(YEAR FROM CURRENT_DATE)::int - 1, EXTRACT(YEAR FROM CURRENT_DATE)::int) AS y) y
-- WHERE NOT EXISTS (
--   SELECT 1 FROM leave_balances b
--   WHERE b.employee_id = e.id
--     AND b.year = y.y
--     AND b.leave_type = 'FL'
-- );
