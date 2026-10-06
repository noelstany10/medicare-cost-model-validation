-- 02_claims_features.sql
-- Claim-level utilisation and diagnosis features per beneficiary-year from
-- Inpatient (Part A) and Outpatient (institutional Part B) claims.

-- 1. Inpatient stays, de-duplicated at claim level (CLM_ID + SEGMENT)
DROP TABLE IF EXISTS ip_stay;
CREATE TABLE ip_stay AS
SELECT DISTINCT
    DESYNPUF_ID AS bene_id,
    CLM_ID,
    CAST(substr(CLM_FROM_DT, 1, 4) AS INTEGER)                         AS year,
    julianday(substr(COALESCE(NULLIF(CLM_ADMSN_DT, ''), CLM_FROM_DT), 1, 4) || '-' ||
              substr(COALESCE(NULLIF(CLM_ADMSN_DT, ''), CLM_FROM_DT), 5, 2) || '-' ||
              substr(COALESCE(NULLIF(CLM_ADMSN_DT, ''), CLM_FROM_DT), 7, 2))   AS admit_jd,
    julianday(substr(CLM_THRU_DT, 1, 4) || '-' || substr(CLM_THRU_DT, 5, 2) || '-' ||
              substr(CLM_THRU_DT, 7, 2))                                AS disch_jd,
    COALESCE(CAST(NULLIF(CLM_UTLZTN_DAY_CNT, '') AS INTEGER), 0)        AS util_days,
    PRVDR_NUM
FROM stg_ip
WHERE CLM_FROM_DT IS NOT NULL AND CLM_FROM_DT <> '';

-- 2. 30-day readmissions (all-cause, any hospital): admission within 30 days of a prior discharge
DROP TABLE IF EXISTS ip_readmit;
CREATE TABLE ip_readmit AS
SELECT bene_id, year, COUNT(*) AS ip_readmit_30d
FROM (
    SELECT bene_id, year, admit_jd,
           LAG(disch_jd) OVER (PARTITION BY bene_id ORDER BY admit_jd) AS prev_disch_jd
    FROM ip_stay
)
WHERE prev_disch_jd IS NOT NULL AND admit_jd - prev_disch_jd BETWEEN 0 AND 30
GROUP BY bene_id, year;

DROP TABLE IF EXISTS ip_util;
CREATE TABLE ip_util AS
SELECT bene_id, year,
       COUNT(DISTINCT CLM_ID)                                      AS ip_admits,
       SUM(MAX(util_days, CAST(disch_jd - admit_jd AS INTEGER)))   AS ip_days
FROM ip_stay GROUP BY bene_id, year;

-- 3. Outpatient visits and ED visits (HCPCS 99281-99285 / revenue-based ED proxy)
DROP TABLE IF EXISTS op_util;
CREATE TABLE op_util AS
SELECT DESYNPUF_ID AS bene_id,
       CAST(substr(CLM_FROM_DT, 1, 4) AS INTEGER) AS year,
       COUNT(DISTINCT CLM_ID) AS op_visits,
       COUNT(DISTINCT CASE WHEN HCPCS_CD_1 BETWEEN '99281' AND '99285' OR HCPCS_CD_2 BETWEEN '99281' AND '99285'
                                OR HCPCS_CD_3 BETWEEN '99281' AND '99285' THEN CLM_ID END) AS er_visits
FROM stg_op
WHERE CLM_FROM_DT IS NOT NULL AND CLM_FROM_DT <> ''
GROUP BY 1, 2;

-- 4. Distinct facility providers seen (IP + OP)
DROP TABLE IF EXISTS prov_util;
CREATE TABLE prov_util AS
SELECT bene_id, year, COUNT(DISTINCT prv) AS n_providers FROM (
    SELECT DESYNPUF_ID AS bene_id, CAST(substr(CLM_FROM_DT,1,4) AS INTEGER) AS year, PRVDR_NUM AS prv FROM stg_ip
    UNION ALL
    SELECT DESYNPUF_ID, CAST(substr(CLM_FROM_DT,1,4) AS INTEGER), PRVDR_NUM FROM stg_op
) WHERE prv IS NOT NULL GROUP BY 1, 2;

-- 5. Diagnosis long table (unpivot ICD-9 dx 1-10 across IP + OP)
DROP TABLE IF EXISTS dx_long;
CREATE TABLE dx_long AS
WITH claims AS (
    SELECT DESYNPUF_ID, CLM_FROM_DT, ICD9_DGNS_CD_1 d1, ICD9_DGNS_CD_2 d2, ICD9_DGNS_CD_3 d3, ICD9_DGNS_CD_4 d4,
           ICD9_DGNS_CD_5 d5, ICD9_DGNS_CD_6 d6, ICD9_DGNS_CD_7 d7, ICD9_DGNS_CD_8 d8, ICD9_DGNS_CD_9 d9, ICD9_DGNS_CD_10 d10
    FROM stg_ip
    UNION ALL
    SELECT DESYNPUF_ID, CLM_FROM_DT, ICD9_DGNS_CD_1, ICD9_DGNS_CD_2, ICD9_DGNS_CD_3, ICD9_DGNS_CD_4,
           ICD9_DGNS_CD_5, ICD9_DGNS_CD_6, ICD9_DGNS_CD_7, ICD9_DGNS_CD_8, ICD9_DGNS_CD_9, ICD9_DGNS_CD_10
    FROM stg_op
), u AS (
              SELECT DESYNPUF_ID, CLM_FROM_DT, d1 AS dx FROM claims
    UNION ALL SELECT DESYNPUF_ID, CLM_FROM_DT, d2 FROM claims
    UNION ALL SELECT DESYNPUF_ID, CLM_FROM_DT, d3 FROM claims
    UNION ALL SELECT DESYNPUF_ID, CLM_FROM_DT, d4 FROM claims
    UNION ALL SELECT DESYNPUF_ID, CLM_FROM_DT, d5 FROM claims
    UNION ALL SELECT DESYNPUF_ID, CLM_FROM_DT, d6 FROM claims
    UNION ALL SELECT DESYNPUF_ID, CLM_FROM_DT, d7 FROM claims
    UNION ALL SELECT DESYNPUF_ID, CLM_FROM_DT, d8 FROM claims
    UNION ALL SELECT DESYNPUF_ID, CLM_FROM_DT, d9 FROM claims
    UNION ALL SELECT DESYNPUF_ID, CLM_FROM_DT, d10 FROM claims
)
SELECT DISTINCT DESYNPUF_ID AS bene_id, CAST(substr(CLM_FROM_DT, 1, 4) AS INTEGER) AS year, dx
FROM u WHERE dx IS NOT NULL AND dx <> '' AND CLM_FROM_DT IS NOT NULL AND CLM_FROM_DT <> '';

-- 6. Clinical condition categories (simplified, HCC-inspired ICD-9 groupings)
DROP TABLE IF EXISTS dx_flags;
CREATE TABLE dx_flags AS
SELECT bene_id, year,
       COUNT(DISTINCT dx) AS n_distinct_dx,
       MAX(dx LIKE '250%')                                                  AS dx_diabetes,
       MAX(dx LIKE '428%' OR dx IN ('40201','40211','40291','40401','40403','40411','40413','40491','40493')) AS dx_chf,
       MAX(substr(dx,1,3) BETWEEN '490' AND '496')                         AS dx_copd,
       MAX(dx LIKE '585%' OR dx LIKE '403%')                               AS dx_ckd,
       MAX(dx IN ('5856') OR dx LIKE 'V451%' OR dx LIKE 'V56%')            AS dx_esrd,
       MAX(substr(dx,1,1) BETWEEN '1' AND '2' AND substr(dx,1,3) BETWEEN '140' AND '208') AS dx_cancer,
       MAX(substr(dx,1,3) BETWEEN '410' AND '414')                         AS dx_ami_ihd,
       MAX(substr(dx,1,3) BETWEEN '430' AND '438')                         AS dx_stroke,
       MAX(dx LIKE '290%' OR dx LIKE '3310%' OR dx LIKE '294%')            AS dx_dementia,
       MAX(dx LIKE '311%' OR dx LIKE '2962%' OR dx LIKE '2963%')           AS dx_depression,
       MAX(substr(dx,1,3) BETWEEN '401' AND '405')                         AS dx_hypertension,
       MAX(dx LIKE '4273%')                                                AS dx_afib
FROM dx_long GROUP BY bene_id, year;
