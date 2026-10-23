-- =========================================================
-- Cricbuzz LiveStats - Database Schema (PostgreSQL)
-- =========================================================

-- ---------- RESET (uncomment only while developing) ----------
-- DROP TABLE IF EXISTS fielding, bowling_innings, batting_innings,
--     player_career_stats, matches, series, players, venues, teams CASCADE;

CREATE TABLE IF NOT EXISTS teams (
    team_id           SERIAL PRIMARY KEY,
    cricbuzz_team_id  INT UNIQUE,
    team_name         VARCHAR(100) NOT NULL UNIQUE,
    team_short_name   VARCHAR(20),
    country           VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS venues (
    venue_id          SERIAL PRIMARY KEY,
    cricbuzz_venue_id INT UNIQUE,
    venue_name        VARCHAR(200) NOT NULL,
    city              VARCHAR(100),
    country           VARCHAR(100),
    capacity          INT CHECK (capacity IS NULL OR capacity >= 0),
    UNIQUE (venue_name, city)
);

CREATE TABLE IF NOT EXISTS players (
    player_id           SERIAL PRIMARY KEY,
    cricbuzz_player_id  INT UNIQUE,
    cricsheet_player_id VARCHAR(20) UNIQUE,
    full_name           VARCHAR(150) NOT NULL,
    country             VARCHAR(100),
    playing_role        VARCHAR(50),
    batting_style       VARCHAR(50),
    bowling_style       VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS series (
    series_id          SERIAL PRIMARY KEY,
    cricbuzz_series_id INT UNIQUE,
    series_name        VARCHAR(200) NOT NULL,
    host_country       VARCHAR(100),
    match_type         VARCHAR(50),
    start_date         DATE,
    end_date           DATE,
    total_matches      INT
);

CREATE TABLE IF NOT EXISTS matches (
    match_id           SERIAL PRIMARY KEY,
    cricbuzz_match_id  INT UNIQUE,
    cricsheet_match_id VARCHAR(20) UNIQUE,
    series_id          INT REFERENCES series(series_id) ON DELETE SET NULL,
    match_desc         VARCHAR(200),
    format             VARCHAR(10) NOT NULL
                       CHECK (format IN ('Test', 'ODI', 'T20I', 'T20')),
    team1_id           INT REFERENCES teams(team_id),
    team2_id           INT REFERENCES teams(team_id),
    venue_id           INT REFERENCES venues(venue_id),
    match_date         DATE NOT NULL,
    toss_winner_id     INT REFERENCES teams(team_id),
    toss_decision      VARCHAR(10) CHECK (toss_decision IN ('bat', 'bowl')),
    winner_id          INT REFERENCES teams(team_id),
    victory_margin     INT,
    victory_type       VARCHAR(20)
                       CHECK (victory_type IN ('runs', 'wickets', 'innings',
                                               'tie', 'draw', 'no result')),
    result_text        VARCHAR(200),
    state              VARCHAR(30),
    source             VARCHAR(20) NOT NULL DEFAULT 'cricbuzz'
                       CHECK (source IN ('cricbuzz', 'cricsheet', 'manual')),
    CHECK (team1_id <> team2_id)
);

CREATE TABLE IF NOT EXISTS batting_innings (
    batting_id       SERIAL PRIMARY KEY,
    match_id         INT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    innings_no       SMALLINT NOT NULL CHECK (innings_no BETWEEN 1 AND 4),
    team_id          INT REFERENCES teams(team_id),
    player_id        INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    batting_position SMALLINT CHECK (batting_position BETWEEN 1 AND 11),
    runs             INT NOT NULL DEFAULT 0 CHECK (runs >= 0),
    balls            INT NOT NULL DEFAULT 0 CHECK (balls >= 0),
    fours            INT DEFAULT 0,
    sixes            INT DEFAULT 0,
    strike_rate      NUMERIC(6, 2),
    is_out           BOOLEAN,
    dismissal        VARCHAR(200),
    UNIQUE (match_id, innings_no, player_id)
);

CREATE TABLE IF NOT EXISTS bowling_innings (
    bowling_id    SERIAL PRIMARY KEY,
    match_id      INT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    innings_no    SMALLINT NOT NULL CHECK (innings_no BETWEEN 1 AND 4),
    team_id       INT REFERENCES teams(team_id),
    player_id     INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    balls_bowled  INT NOT NULL CHECK (balls_bowled >= 0),
    overs         VARCHAR(6),
    maidens       INT DEFAULT 0,
    runs_conceded INT NOT NULL DEFAULT 0,
    wickets       INT NOT NULL DEFAULT 0 CHECK (wickets BETWEEN 0 AND 10),
    economy       NUMERIC(5, 2),
    UNIQUE (match_id, innings_no, player_id)
);

CREATE TABLE IF NOT EXISTS fielding (
    match_id   INT NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    player_id  INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    catches    INT NOT NULL DEFAULT 0,
    stumpings  INT NOT NULL DEFAULT 0,
    run_outs   INT NOT NULL DEFAULT 0,
    PRIMARY KEY (match_id, player_id)
);

CREATE TABLE IF NOT EXISTS player_career_stats (
    player_id      INT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    format         VARCHAR(10) NOT NULL CHECK (format IN ('Test', 'ODI', 'T20I')),
    matches        INT DEFAULT 0,
    innings        INT DEFAULT 0,
    not_outs       INT DEFAULT 0,
    runs           INT DEFAULT 0,
    balls_faced    INT DEFAULT 0,
    highest_score  INT,
    batting_avg    NUMERIC(6, 2),
    strike_rate    NUMERIC(6, 2),
    fours          INT DEFAULT 0,
    sixes          INT DEFAULT 0,
    fifties        INT DEFAULT 0,
    hundreds       INT DEFAULT 0,
    bowl_innings   INT DEFAULT 0,
    balls_bowled   INT DEFAULT 0,
    runs_conceded  INT DEFAULT 0,
    wickets        INT DEFAULT 0,
    bowling_avg    NUMERIC(6, 2),
    economy        NUMERIC(5, 2),
    best_bowling   VARCHAR(10),
    five_wickets   INT DEFAULT 0,
    PRIMARY KEY (player_id, format)
);

CREATE INDEX IF NOT EXISTS idx_matches_date    ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_format  ON matches(format);
CREATE INDEX IF NOT EXISTS idx_matches_venue   ON matches(venue_id);
CREATE INDEX IF NOT EXISTS idx_bat_player      ON batting_innings(player_id);
CREATE INDEX IF NOT EXISTS idx_bat_match       ON batting_innings(match_id, innings_no);
CREATE INDEX IF NOT EXISTS idx_bowl_player     ON bowling_innings(player_id);
CREATE INDEX IF NOT EXISTS idx_bowl_match      ON bowling_innings(match_id);
CREATE INDEX IF NOT EXISTS idx_players_country ON players(country);