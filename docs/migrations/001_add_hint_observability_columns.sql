ALTER TABLE interaction_logs ADD COLUMN leakage_score INT DEFAULT 0;
ALTER TABLE interaction_logs ADD COLUMN rewrite_count INT DEFAULT 0;
ALTER TABLE interaction_logs ADD COLUMN leakage_reason VARCHAR(255);
ALTER TABLE interaction_logs ADD COLUMN hint_strength VARCHAR(32);
ALTER TABLE interaction_logs ADD COLUMN pedagogical_intent VARCHAR(64);
ALTER TABLE interaction_logs ADD COLUMN hint_safety_status VARCHAR(64);
ALTER TABLE interaction_logs ADD INDEX idx_interaction_hint_strength (hint_strength);
ALTER TABLE interaction_logs ADD INDEX idx_interaction_pedagogical_intent (pedagogical_intent);
