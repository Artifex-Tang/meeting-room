-- Create test schema for pytest (idempotent)
CREATE DATABASE IF NOT EXISTS meeting_test
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON meeting_test.* TO 'meeting'@'%';
