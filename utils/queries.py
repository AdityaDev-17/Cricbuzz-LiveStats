"""The 25 SQL practice queries (PostgreSQL)."""

QUERIES = [
    # ======================= BEGINNER (1-8) =======================
    {
        "id": 1,
        "level": "Beginner",
        "title": "Players who represent India",
        "question": "Find all players who represent India. Display their full name, playing role, "
        "batting style, and bowling style.",
        "sql": """
SELECT full_name, playing_role, batting_style, bowling_style
FROM players
WHERE country = 'India'
ORDER BY playing_role NULLS LAST, full_name;
""",
    },
    {
        "id": 2,
        "level": "Beginner",
        "title": "Matches in the last 30 days",
        "question": "Show all cricket matches played in the last 30 days with description, both teams, "
        "venue with city, and date. Most recent first.",
        "sql": """
SELECT m.match_desc, t1.team_name AS team1, t2.team_name AS team2,
       v.venue_name || COALESCE(', ' || v.city, '') AS venue, m.match_date
FROM matches m
JOIN teams t1 ON t1.team_id = m.team1_id
JOIN teams t2 ON t2.team_id = m.team2_id
LEFT JOIN venues v ON v.venue_id = m.venue_id
WHERE m.match_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY m.match_date DESC;
""",
    },
    {
        "id": 3,
        "level": "Beginner",
        "title": "Top 10 ODI run scorers",
        "question": "List the top 10 highest run scorers in ODI cricket with total runs, batting average "
        "and centuries.",
        "sql": """
SELECT p.full_name AS player, c.runs AS total_runs, c.batting_avg, c.hundreds AS centuries
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
WHERE c.format = 'ODI'
ORDER BY c.runs DESC NULLS LAST
LIMIT 10;
""",
    },
    {
        "id": 4,
        "level": "Beginner",
        "title": "Venues with capacity over 50,000",
        "question": "Display venues with seating capacity above 50,000 with name, city, country and capacity.",
        "sql": """
SELECT venue_name, city, country, capacity
FROM venues
WHERE capacity > 50000
ORDER BY capacity DESC;
""",
    },
    {
        "id": 5,
        "level": "Beginner",
        "title": "Wins per team",
        "question": "Calculate how many matches each team has won. Most wins first.",
        "sql": """
SELECT t.team_name, COUNT(*) AS total_wins
FROM matches m
JOIN teams t ON t.team_id = m.winner_id
GROUP BY t.team_name
ORDER BY total_wins DESC;
""",
    },
    {
        "id": 6,
        "level": "Beginner",
        "title": "Players per playing role",
        "question": "Count how many players belong to each playing role.",
        "sql": """
SELECT playing_role, COUNT(*) AS players
FROM players
WHERE playing_role IS NOT NULL
GROUP BY playing_role
ORDER BY players DESC;
""",
    },
    {
        "id": 7,
        "level": "Beginner",
        "title": "Highest individual score per format",
        "question": "Find the highest individual batting score in each format (Test, ODI, T20I).",
        "sql": """
SELECT DISTINCT ON (m.format)
       m.format, b.runs AS highest_score, p.full_name AS player, m.match_date
FROM batting_innings b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
ORDER BY m.format, b.runs DESC;
""",
    },
    {
        "id": 8,
        "level": "Beginner",
        "title": "Series that started in 2024",
        "question": "Show all series that started in 2024 with name, host country, match type, start date "
        "and total matches.",
        "sql": """
SELECT series_name, host_country, match_type, start_date, total_matches
FROM series
WHERE EXTRACT(YEAR FROM start_date) = 2024
ORDER BY start_date;
""",
    },
    # ======================= INTERMEDIATE (9-16) =======================
    {
        "id": 9,
        "level": "Intermediate",
        "title": "All-rounders: 1000+ runs and 50+ wickets",
        "question": "Find all-rounders with more than 1000 runs AND more than 50 wickets, per format.",
        "sql": """
SELECT p.full_name AS player, c.format, c.runs AS total_runs, c.wickets AS total_wickets
FROM player_career_stats c
JOIN players p ON p.player_id = c.player_id
WHERE c.runs > 1000 AND c.wickets > 50
ORDER BY c.runs + c.wickets * 20 DESC;
""",
    },
    {
        "id": 10,
        "level": "Intermediate",
        "title": "Last 20 completed matches",
        "question": "Details of the last 20 completed matches: teams, winner, margin, victory type, venue.",
        "sql": """
SELECT m.match_desc, t1.team_name AS team1, t2.team_name AS team2,
       w.team_name AS winner, m.victory_margin, m.victory_type, v.venue_name, m.match_date
FROM matches m
JOIN teams t1 ON t1.team_id = m.team1_id
JOIN teams t2 ON t2.team_id = m.team2_id
LEFT JOIN teams w ON w.team_id = m.winner_id
LEFT JOIN venues v ON v.venue_id = m.venue_id
WHERE m.state = 'Complete'
ORDER BY m.match_date DESC
LIMIT 20;
""",
    },
    {
        "id": 11,
        "level": "Intermediate",
        "title": "Runs across formats",
        "question": "For players with at least 2 formats, show Test, ODI and T20I runs plus overall average.",
        "sql": """
SELECT p.full_name AS player,
       SUM(CASE WHEN m.format = 'Test' THEN b.runs ELSE 0 END) AS test_runs,
       SUM(CASE WHEN m.format = 'ODI'  THEN b.runs ELSE 0 END) AS odi_runs,
       SUM(CASE WHEN m.format = 'T20I' THEN b.runs ELSE 0 END) AS t20i_runs,
       ROUND(CAST(SUM(b.runs) AS NUMERIC) /
             NULLIF(SUM(CASE WHEN b.is_out THEN 1 ELSE 0 END), 0), 2) AS overall_average
FROM batting_innings b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
GROUP BY p.player_id, p.full_name
HAVING COUNT(DISTINCT m.format) >= 2
ORDER BY SUM(b.runs) DESC;
""",
    },
    {
        "id": 12,
        "level": "Intermediate",
        "title": "Home vs away wins",
        "question": "Count each team's wins at home vs away (home = venue country matches team country).",
        "sql": """
WITH team_matches AS (
    SELECT m.match_id, m.team1_id AS team_id, m.winner_id, v.country AS venue_country
    FROM matches m JOIN venues v ON v.venue_id = m.venue_id
    WHERE v.country IS NOT NULL
    UNION ALL
    SELECT m.match_id, m.team2_id, m.winner_id, v.country
    FROM matches m JOIN venues v ON v.venue_id = m.venue_id
    WHERE v.country IS NOT NULL
)
SELECT t.team_name,
       COUNT(*) FILTER (WHERE tm.venue_country = t.country)  AS home_matches,
       COUNT(*) FILTER (WHERE tm.venue_country = t.country  AND tm.winner_id = t.team_id) AS home_wins,
       COUNT(*) FILTER (WHERE tm.venue_country <> t.country) AS away_matches,
       COUNT(*) FILTER (WHERE tm.venue_country <> t.country AND tm.winner_id = t.team_id) AS away_wins
FROM team_matches tm
JOIN teams t ON t.team_id = tm.team_id
GROUP BY t.team_name
ORDER BY home_wins + away_wins DESC;
""",
    },
    {
        "id": 13,
        "level": "Intermediate",
        "title": "100+ run partnerships (consecutive batters)",
        "question": "Batting partnerships where consecutive batsmen scored a combined 100+ in the same innings.",
        "sql": """
SELECT p1.full_name AS batter_1, p2.full_name AS batter_2,
       b1.batting_position || '-' || b2.batting_position AS positions,
       b1.runs + b2.runs AS partnership_runs, b1.innings_no,
       m.format, m.match_desc, m.match_date
FROM batting_innings b1
JOIN batting_innings b2
  ON b2.match_id = b1.match_id
 AND b2.innings_no = b1.innings_no
 AND b2.batting_position = b1.batting_position + 1
JOIN players p1 ON p1.player_id = b1.player_id
JOIN players p2 ON p2.player_id = b2.player_id
JOIN matches m  ON m.match_id  = b1.match_id
WHERE b1.runs + b2.runs >= 100
ORDER BY partnership_runs DESC
LIMIT 100;
""",
    },
    {
        "id": 14,
        "level": "Intermediate",
        "title": "Bowling performance by venue",
        "question": "Bowlers with 3+ matches at the same venue (4+ overs each): average economy, wickets, matches.",
        "sql": """
SELECT p.full_name AS bowler, v.venue_name,
       COUNT(DISTINCT w.match_id) AS matches,
       SUM(w.wickets) AS total_wickets,
       ROUND(AVG(w.economy), 2) AS avg_economy
FROM bowling_innings w
JOIN matches m ON m.match_id = w.match_id
JOIN venues v  ON v.venue_id = m.venue_id
JOIN players p ON p.player_id = w.player_id
WHERE w.balls_bowled >= 24
GROUP BY p.player_id, p.full_name, v.venue_id, v.venue_name
HAVING COUNT(DISTINCT w.match_id) >= 3
ORDER BY avg_economy;
""",
    },
    {
        "id": 15,
        "level": "Intermediate",
        "title": "Performers in close matches",
        "question": "Close match = won by < 50 runs or < 5 wickets. Player average runs, close matches played, "
        "and close matches won by their team.",
        "sql": """
WITH close_matches AS (
    SELECT match_id, winner_id
    FROM matches
    WHERE (victory_type = 'runs' AND victory_margin < 50)
       OR (victory_type = 'wickets' AND victory_margin < 5)
)
SELECT p.full_name AS player,
       COUNT(DISTINCT b.match_id) AS close_matches,
       ROUND(AVG(b.runs), 2) AS avg_runs,
       COUNT(DISTINCT CASE WHEN cm.winner_id = b.team_id THEN b.match_id END) AS close_matches_won
FROM batting_innings b
JOIN close_matches cm ON cm.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
GROUP BY p.player_id, p.full_name
HAVING COUNT(DISTINCT b.match_id) >= 5
ORDER BY avg_runs DESC;
""",
    },
    {
        "id": 16,
        "level": "Intermediate",
        "title": "Yearly batting performance since 2020",
        "question": "Per player per year since 2020: average runs per match and average strike rate "
        "(players with 5+ matches that year).",
        "sql": """
SELECT p.full_name AS player,
       CAST(EXTRACT(YEAR FROM m.match_date) AS INT) AS season_year,
       COUNT(DISTINCT b.match_id) AS matches,
       ROUND(CAST(SUM(b.runs) AS NUMERIC) / COUNT(DISTINCT b.match_id), 2) AS avg_runs_per_match,
       ROUND(AVG(b.strike_rate), 2) AS avg_strike_rate
FROM batting_innings b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE m.match_date >= DATE '2020-01-01'
GROUP BY p.player_id, p.full_name, CAST(EXTRACT(YEAR FROM m.match_date) AS INT)
HAVING COUNT(DISTINCT b.match_id) >= 5
ORDER BY player, season_year;
""",
    },
    # ======================= ADVANCED (17-25) =======================
    {
        "id": 17,
        "level": "Advanced",
        "title": "Does winning the toss help?",
        "question": "Percentage of matches won by the toss winner, broken down by toss decision.",
        "sql": """
SELECT COALESCE(format, 'All formats') AS format, toss_decision,
       COUNT(*) AS matches,
       COUNT(*) FILTER (WHERE winner_id = toss_winner_id) AS toss_winner_won,
       ROUND(100.0 * COUNT(*) FILTER (WHERE winner_id = toss_winner_id) / COUNT(*), 2) AS win_pct
FROM matches
WHERE toss_winner_id IS NOT NULL AND toss_decision IS NOT NULL AND winner_id IS NOT NULL
GROUP BY GROUPING SETS ((toss_decision), (format, toss_decision))
ORDER BY format NULLS FIRST, toss_decision;
""",
    },
    {
        "id": 18,
        "level": "Advanced",
        "title": "Most economical limited-overs bowlers",
        "question": "Economy rate and wickets in ODI + T20I for bowlers with 10+ matches and 2+ overs per match.",
        "sql": """
SELECT p.full_name AS bowler,
       COUNT(DISTINCT w.match_id) AS matches,
       SUM(w.wickets) AS total_wickets,
       ROUND(SUM(w.runs_conceded) * 6.0 / NULLIF(SUM(w.balls_bowled), 0), 2) AS economy_rate,
       ROUND(SUM(w.balls_bowled) / 6.0 / COUNT(DISTINCT w.match_id), 2) AS avg_overs_per_match
FROM bowling_innings w
JOIN matches m ON m.match_id = w.match_id
JOIN players p ON p.player_id = w.player_id
WHERE m.format IN ('ODI', 'T20I')
GROUP BY p.player_id, p.full_name
HAVING COUNT(DISTINCT w.match_id) >= 10
   AND SUM(w.balls_bowled) * 1.0 / COUNT(DISTINCT w.match_id) >= 12
ORDER BY economy_rate
LIMIT 25;
""",
    },
    {
        "id": 19,
        "level": "Advanced",
        "title": "Most consistent batsmen",
        "question": "Average and standard deviation of runs (innings with 10+ balls, since 2022). "
        "Lower SD = more consistent.",
        "sql": """
SELECT p.full_name AS player,
       COUNT(*) AS innings,
       ROUND(AVG(b.runs), 2) AS avg_runs,
       ROUND(STDDEV_SAMP(b.runs), 2) AS stddev_runs
FROM batting_innings b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
WHERE b.balls >= 10 AND m.match_date >= DATE '2022-01-01'
GROUP BY p.player_id, p.full_name
HAVING COUNT(*) >= 10
ORDER BY stddev_runs ASC
LIMIT 25;
""",
    },
    {
        "id": 20,
        "level": "Advanced",
        "title": "Matches and average per format",
        "question": "Test, ODI and T20I match counts and batting averages for players with 20+ total matches.",
        "sql": """
SELECT p.full_name AS player,
       COUNT(DISTINCT m.match_id) FILTER (WHERE m.format = 'Test') AS test_matches,
       COUNT(DISTINCT m.match_id) FILTER (WHERE m.format = 'ODI')  AS odi_matches,
       COUNT(DISTINCT m.match_id) FILTER (WHERE m.format = 'T20I') AS t20i_matches,
       ROUND(CAST(SUM(b.runs) FILTER (WHERE m.format = 'Test') AS NUMERIC) /
             NULLIF(COUNT(*) FILTER (WHERE m.format = 'Test' AND b.is_out), 0), 2) AS test_avg,
       ROUND(CAST(SUM(b.runs) FILTER (WHERE m.format = 'ODI') AS NUMERIC) /
             NULLIF(COUNT(*) FILTER (WHERE m.format = 'ODI' AND b.is_out), 0), 2) AS odi_avg,
       ROUND(CAST(SUM(b.runs) FILTER (WHERE m.format = 'T20I') AS NUMERIC) /
             NULLIF(COUNT(*) FILTER (WHERE m.format = 'T20I' AND b.is_out), 0), 2) AS t20i_avg,
       COUNT(DISTINCT m.match_id) AS total_matches
FROM batting_innings b
JOIN matches m ON m.match_id = b.match_id
JOIN players p ON p.player_id = b.player_id
GROUP BY p.player_id, p.full_name
HAVING COUNT(DISTINCT m.match_id) >= 20
ORDER BY total_matches DESC;
""",
    },
    {
        "id": 21,
        "level": "Advanced",
        "title": "Weighted performance ranking",
        "question": "Combine batting, bowling and fielding into a weighted score and rank the top 10 per format.",
        "sql": """
WITH bat AS (
    SELECT b.player_id, m.format, COUNT(DISTINCT b.match_id) AS matches, SUM(b.runs) AS runs,
           COALESCE(CAST(SUM(b.runs) AS NUMERIC) /
                    NULLIF(SUM(CASE WHEN b.is_out THEN 1 ELSE 0 END), 0), 0) AS bat_avg,
           COALESCE(SUM(b.runs) * 100.0 / NULLIF(SUM(b.balls), 0), 0) AS strike_rate
    FROM batting_innings b JOIN matches m ON m.match_id = b.match_id
    GROUP BY b.player_id, m.format
),
bowl AS (
    SELECT w.player_id, m.format, COUNT(DISTINCT w.match_id) AS matches, SUM(w.wickets) AS wickets,
           CAST(SUM(w.runs_conceded) AS NUMERIC) / NULLIF(SUM(w.wickets), 0) AS bowl_avg,
           SUM(w.runs_conceded) * 6.0 / NULLIF(SUM(w.balls_bowled), 0) AS economy
    FROM bowling_innings w JOIN matches m ON m.match_id = w.match_id
    GROUP BY w.player_id, m.format
),
fld AS (
    SELECT f.player_id, m.format, SUM(f.catches) AS catches, SUM(f.stumpings) AS stumpings
    FROM fielding f JOIN matches m ON m.match_id = f.match_id
    GROUP BY f.player_id, m.format
),
scores AS (
    SELECT COALESCE(bat.player_id, bowl.player_id) AS player_id,
           COALESCE(bat.format, bowl.format) AS format,
           GREATEST(COALESCE(bat.matches, 0), COALESCE(bowl.matches, 0)) AS matches,
           COALESCE(bat.runs, 0) * 0.01 + COALESCE(bat.bat_avg, 0) * 0.5
               + COALESCE(bat.strike_rate, 0) * 0.3 AS batting_points,
           CASE WHEN COALESCE(bowl.wickets, 0) > 0
                THEN bowl.wickets * 2 + (50 - bowl.bowl_avg) * 0.5 + (6 - bowl.economy) * 2
                ELSE 0 END AS bowling_points,
           COALESCE(fld.catches, 0) * 3 + COALESCE(fld.stumpings, 0) * 5 AS fielding_points
    FROM bat
    FULL OUTER JOIN bowl ON bowl.player_id = bat.player_id AND bowl.format = bat.format
    LEFT JOIN fld ON fld.player_id = COALESCE(bat.player_id, bowl.player_id)
                 AND fld.format = COALESCE(bat.format, bowl.format)
),
ranked AS (
    SELECT s.*, s.batting_points + s.bowling_points + s.fielding_points AS total_points,
           RANK() OVER (PARTITION BY s.format
                        ORDER BY s.batting_points + s.bowling_points + s.fielding_points DESC) AS format_rank
    FROM scores s
    WHERE s.matches >= 10
)
SELECT r.format, r.format_rank, p.full_name AS player, p.country, r.matches,
       ROUND(r.batting_points, 2) AS batting_points,
       ROUND(r.bowling_points, 2) AS bowling_points,
       ROUND(r.fielding_points, 2) AS fielding_points,
       ROUND(r.total_points, 2) AS total_points
FROM ranked r
JOIN players p ON p.player_id = r.player_id
WHERE r.format_rank <= 10
ORDER BY r.format, r.format_rank;
""",
    },
    {
        "id": 22,
        "level": "Advanced",
        "title": "Head-to-head analysis",
        "question": "Team pairs with 5+ meetings in the last 3 years: wins, win %, average margins, "
        "batting-first vs chasing wins.",
        "sql": """
WITH recent AS (
    SELECT m.*,
           LEAST(m.team1_id, m.team2_id)    AS team_a,
           GREATEST(m.team1_id, m.team2_id) AS team_b,
           CASE WHEN m.toss_decision = 'bat'  THEN m.toss_winner_id
                WHEN m.toss_decision = 'bowl' THEN
                     CASE WHEN m.toss_winner_id = m.team1_id THEN m.team2_id ELSE m.team1_id END
           END AS bat_first_id
    FROM matches m
    WHERE m.match_date >= CURRENT_DATE - INTERVAL '3 years'
)
SELECT ta.team_name AS team_a, tb.team_name AS team_b,
       COUNT(*) AS matches,
       COUNT(DISTINCT r.venue_id) AS venues_played,
       COUNT(*) FILTER (WHERE r.winner_id = r.team_a) AS team_a_wins,
       COUNT(*) FILTER (WHERE r.winner_id = r.team_b) AS team_b_wins,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.winner_id = r.team_a) / COUNT(*), 1) AS team_a_win_pct,
       ROUND(100.0 * COUNT(*) FILTER (WHERE r.winner_id = r.team_b) / COUNT(*), 1) AS team_b_win_pct,
       ROUND(AVG(r.victory_margin) FILTER (WHERE r.winner_id = r.team_a
             AND r.victory_type IN ('runs', 'innings')), 1) AS team_a_avg_margin_runs,
       ROUND(AVG(r.victory_margin) FILTER (WHERE r.winner_id = r.team_a
             AND r.victory_type = 'wickets'), 1) AS team_a_avg_margin_wkts,
       ROUND(AVG(r.victory_margin) FILTER (WHERE r.winner_id = r.team_b
             AND r.victory_type IN ('runs', 'innings')), 1) AS team_b_avg_margin_runs,
       ROUND(AVG(r.victory_margin) FILTER (WHERE r.winner_id = r.team_b
             AND r.victory_type = 'wickets'), 1) AS team_b_avg_margin_wkts,
       COUNT(*) FILTER (WHERE r.winner_id = r.team_a AND r.bat_first_id = r.team_a) AS team_a_wins_batting_first,
       COUNT(*) FILTER (WHERE r.winner_id = r.team_a AND r.bat_first_id = r.team_b) AS team_a_wins_chasing,
       COUNT(*) FILTER (WHERE r.winner_id = r.team_b AND r.bat_first_id = r.team_b) AS team_b_wins_batting_first,
       COUNT(*) FILTER (WHERE r.winner_id = r.team_b AND r.bat_first_id = r.team_a) AS team_b_wins_chasing
FROM recent r
JOIN teams ta ON ta.team_id = r.team_a
JOIN teams tb ON tb.team_id = r.team_b
GROUP BY ta.team_name, tb.team_name
HAVING COUNT(*) >= 5
ORDER BY matches DESC;
""",
    },
    {
        "id": 23,
        "level": "Advanced",
        "title": "Recent form and momentum",
        "question": "Last 10 innings per player: last-5 vs last-10 average, strike-rate trend, 50+ scores, "
        "consistency, and a form category.",
        "sql": """
WITH ranked AS (
    SELECT b.player_id, b.runs, b.strike_rate,
           ROW_NUMBER() OVER (PARTITION BY b.player_id
                              ORDER BY m.match_date DESC, b.innings_no DESC) AS rn
    FROM batting_innings b
    JOIN matches m ON m.match_id = b.match_id
),
last10 AS (
    SELECT player_id,
           AVG(runs) FILTER (WHERE rn <= 5) AS avg_last5,
           AVG(runs) AS avg_last10,
           AVG(strike_rate) FILTER (WHERE rn <= 5) AS sr_last5,
           AVG(strike_rate) AS sr_last10,
           COUNT(*) FILTER (WHERE runs >= 50) AS scores_50_plus,
           STDDEV_SAMP(runs) AS sd_runs
    FROM ranked
    WHERE rn <= 10
    GROUP BY player_id
    HAVING COUNT(*) = 10
)
SELECT p.full_name AS player, p.country,
       ROUND(l.avg_last5, 2) AS avg_last_5,
       ROUND(l.avg_last10, 2) AS avg_last_10,
       ROUND(l.sr_last5, 2) AS sr_last_5,
       ROUND(l.sr_last10, 2) AS sr_last_10,
       CASE WHEN l.sr_last5 > l.sr_last10 THEN 'Rising' ELSE 'Falling' END AS sr_trend,
       l.scores_50_plus,
       ROUND(l.avg_last10 / NULLIF(l.sd_runs, 0), 2) AS consistency_score,
       CASE WHEN l.avg_last5 >= 50 AND l.scores_50_plus >= 3 THEN 'Excellent Form'
            WHEN l.avg_last5 >= 35 THEN 'Good Form'
            WHEN l.avg_last5 >= 20 THEN 'Average Form'
            ELSE 'Poor Form' END AS form
FROM last10 l
JOIN players p ON p.player_id = l.player_id
ORDER BY l.avg_last5 DESC;
""",
    },
    {
        "id": 24,
        "level": "Advanced",
        "title": "Best batting partnerships",
        "question": "Pairs of consecutive batsmen with 5+ partnerships: average, 50+ count, highest, success rate.",
        "sql": """
WITH pairs AS (
    SELECT LEAST(b1.player_id, b2.player_id)    AS player_a,
           GREATEST(b1.player_id, b2.player_id) AS player_b,
           b1.runs + b2.runs AS partnership_runs
    FROM batting_innings b1
    JOIN batting_innings b2
      ON b2.match_id = b1.match_id
     AND b2.innings_no = b1.innings_no
     AND b2.batting_position = b1.batting_position + 1
)
SELECT pa.full_name AS batter_1, pb.full_name AS batter_2,
       COUNT(*) AS partnerships,
       ROUND(AVG(partnership_runs), 2) AS avg_partnership,
       COUNT(*) FILTER (WHERE partnership_runs > 50) AS fifty_plus,
       MAX(partnership_runs) AS highest,
       ROUND(100.0 * COUNT(*) FILTER (WHERE partnership_runs > 50) / COUNT(*), 2) AS success_rate_pct
FROM pairs
JOIN players pa ON pa.player_id = pairs.player_a
JOIN players pb ON pb.player_id = pairs.player_b
GROUP BY pa.full_name, pb.full_name
HAVING COUNT(*) >= 5
ORDER BY success_rate_pct DESC, avg_partnership DESC
LIMIT 50;
""",
    },
    {
        "id": 25,
        "level": "Advanced",
        "title": "Career trajectory (quarterly time series)",
        "question": "Quarterly averages for runs and strike rate, compared to the previous quarter, "
        "classified as Career Ascending / Declining / Stable (6+ quarters, 3+ matches each).",
        "sql": """
WITH quarterly AS (
    SELECT b.player_id,
           DATE_TRUNC('quarter', m.match_date) AS quarter,
           COUNT(DISTINCT b.match_id) AS matches,
           AVG(b.runs) AS avg_runs,
           AVG(b.strike_rate) AS avg_sr
    FROM batting_innings b
    JOIN matches m ON m.match_id = b.match_id
    GROUP BY b.player_id, DATE_TRUNC('quarter', m.match_date)
    HAVING COUNT(DISTINCT b.match_id) >= 3
),
compared AS (
    SELECT q.*,
           LAG(q.avg_runs) OVER (PARTITION BY q.player_id ORDER BY q.quarter) AS prev_avg_runs
    FROM quarterly q
),
labelled AS (
    SELECT c.*,
           CASE WHEN c.prev_avg_runs IS NULL THEN NULL
                WHEN c.avg_runs > c.prev_avg_runs * 1.10 THEN 'Improving'
                WHEN c.avg_runs < c.prev_avg_runs * 0.90 THEN 'Declining'
                ELSE 'Stable' END AS trend
    FROM compared c
),
career AS (
    SELECT player_id,
           COUNT(*) AS quarters,
           ROUND((ARRAY_AGG(avg_runs ORDER BY quarter))[1], 2) AS first_qtr_avg,
           ROUND((ARRAY_AGG(avg_runs ORDER BY quarter DESC))[1], 2) AS latest_qtr_avg,
           ROUND(AVG(avg_sr), 2) AS avg_strike_rate,
           COUNT(*) FILTER (WHERE trend = 'Improving') AS improving_qtrs,
           COUNT(*) FILTER (WHERE trend = 'Declining') AS declining_qtrs,
           COUNT(*) FILTER (WHERE trend = 'Stable')    AS stable_qtrs
    FROM labelled
    GROUP BY player_id
    HAVING COUNT(*) >= 6
)
SELECT p.full_name AS player, p.country, c.quarters, c.first_qtr_avg, c.latest_qtr_avg,
       c.avg_strike_rate, c.improving_qtrs, c.declining_qtrs, c.stable_qtrs,
       CASE WHEN c.improving_qtrs > c.declining_qtrs THEN 'Career Ascending'
            WHEN c.declining_qtrs > c.improving_qtrs THEN 'Career Declining'
            ELSE 'Career Stable' END AS career_phase
FROM career c
JOIN players p ON p.player_id = c.player_id
ORDER BY career_phase, c.latest_qtr_avg DESC;
""",
    },
]
