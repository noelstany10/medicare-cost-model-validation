-- 03_model_dataset.sql
-- Prospective modelling dataset: features from year t, target = Medicare paid cost in year t+1.
-- Population (eligibility) rules are recorded as flags so the exclusion waterfall is auditable.

DROP TABLE IF EXISTS model_base;
CREATE TABLE model_base AS
SELECT
    f.*,
    COALESCE(ip.ip_admits, 0)        AS ip_admits,
    COALESCE(ip.ip_days, 0)          AS ip_days,
    COALESCE(rd.ip_readmit_30d, 0)   AS ip_readmit_30d,
    COALESCE(op.op_visits, 0)        AS op_visits,
    COALESCE(op.er_visits, 0)        AS er_visits,
    COALESCE(pv.n_providers, 0)      AS n_providers,
    COALESCE(dx.n_distinct_dx, 0)    AS n_distinct_dx,
    COALESCE(dx.dx_diabetes, 0) AS dx_diabetes,  COALESCE(dx.dx_chf, 0)    AS dx_chf,
    COALESCE(dx.dx_copd, 0)     AS dx_copd,      COALESCE(dx.dx_ckd, 0)    AS dx_ckd,
    COALESCE(dx.dx_esrd, 0)     AS dx_esrd,      COALESCE(dx.dx_cancer, 0) AS dx_cancer,
    COALESCE(dx.dx_ami_ihd, 0)  AS dx_ami_ihd,   COALESCE(dx.dx_stroke, 0) AS dx_stroke,
    COALESCE(dx.dx_dementia, 0) AS dx_dementia,  COALESCE(dx.dx_depression, 0) AS dx_depression,
    COALESCE(dx.dx_hypertension, 0) AS dx_hypertension, COALESCE(dx.dx_afib, 0) AS dx_afib,
    -- next-year outcome
    t.year                AS target_year,
    t.paid_total          AS target_paid,
    t.paid_ip             AS target_paid_ip,
    t.part_a_mos          AS target_part_a_mos,
    t.part_b_mos          AS target_part_b_mos,
    t.death_dt            AS target_death_dt,
    -- eligibility flags
    (t.bene_id IS NOT NULL)                                                 AS elig_in_next_year,
    (f.death_dt IS NULL)                                                    AS elig_alive_end_of_base,
    (f.part_a_mos > 0 OR f.part_b_mos > 0)                                  AS elig_base_coverage,
    (COALESCE(t.part_a_mos, 0) > 0 OR COALESCE(t.part_b_mos, 0) > 0)        AS elig_next_coverage
FROM member_year f
LEFT JOIN member_year t  ON t.bene_id = f.bene_id AND t.year = f.year + 1
LEFT JOIN ip_util     ip ON ip.bene_id = f.bene_id AND ip.year = f.year
LEFT JOIN ip_readmit  rd ON rd.bene_id = f.bene_id AND rd.year = f.year
LEFT JOIN op_util     op ON op.bene_id = f.bene_id AND op.year = f.year
LEFT JOIN prov_util   pv ON pv.bene_id = f.bene_id AND pv.year = f.year
LEFT JOIN dx_flags    dx ON dx.bene_id = f.bene_id AND dx.year = f.year
WHERE f.year IN (2008, 2009);

-- Population waterfall for the validation report
DROP TABLE IF EXISTS population_waterfall;
CREATE TABLE population_waterfall AS
SELECT year AS feature_year, 1 AS step, 'All beneficiaries in base-year summary file' AS rule, COUNT(*) AS n FROM model_base GROUP BY year
UNION ALL SELECT year, 2, 'Alive at end of base year', SUM(elig_alive_end_of_base) FROM model_base GROUP BY year
UNION ALL SELECT year, 3, '+ Part A or B coverage in base year', SUM(elig_alive_end_of_base * elig_base_coverage) FROM model_base GROUP BY year
UNION ALL SELECT year, 4, '+ Present in next-year summary file', SUM(elig_alive_end_of_base * elig_base_coverage * elig_in_next_year) FROM model_base GROUP BY year
UNION ALL SELECT year, 5, '+ Part A or B coverage in next year (final)', SUM(elig_alive_end_of_base * elig_base_coverage * elig_in_next_year * elig_next_coverage) FROM model_base GROUP BY year;

DROP TABLE IF EXISTS model_dataset;
CREATE TABLE model_dataset AS
SELECT * FROM model_base
WHERE elig_alive_end_of_base = 1 AND elig_base_coverage = 1 AND elig_in_next_year = 1 AND elig_next_coverage = 1;
