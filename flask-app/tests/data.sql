INSERT INTO user (username, email, google_id, name)
VALUES
  ('test', 'test@example.com', 'test_google_id_123', 'Test User'),
  ('other', 'other@example.com', 'other_google_id_456', 'Other User');

INSERT INTO post (title, body, author_id, created)
VALUES
  ('test title', 'test' || x'0a' || 'body', 1, '2018-01-01 00:00:00');
