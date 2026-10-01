-- Add address column to students table for Google Maps integration
ALTER TABLE students
ADD COLUMN IF NOT EXISTS address text DEFAULT '';

COMMENT ON COLUMN students.address IS 'Student physical address for Google Maps directions';
