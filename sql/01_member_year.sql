-- 01_member_year.sql
-- One row per beneficiary per calendar year from the annual Beneficiary Summary Files.
-- Derives demographics, coverage exposure, chronic-condition flags and annual cost by setting.

DROP TABLE IF EXISTS member_year;
CREATE TABLE member_year AS
SELECT
    b.DESYNPUF_ID                                              AS bene_id,
    CAST(b.FILE_YEAR AS INTEGER)                               AS year,
    CAST(b.FILE_YEAR AS INTEGER) - CAST(substr(b.BENE_BIRTH_DT, 1, 4) AS INTEGER) AS age,
    CASE WHEN b.BENE_SEX_IDENT_CD = '2' THEN 1 ELSE 0 END      AS is_female,
    CAST(b.BENE_RACE_CD AS INTEGER)                            AS race_cd,       -- fairness testing only
    CASE WHEN b.BENE_ESRD_IND = 'Y' THEN 1 ELSE 0 END          AS esrd,
    CAST(b.SP_STATE_CODE AS INTEGER)                           AS state_cd,
    CASE WHEN b.BENE_DEATH_DT IS NOT NULL AND b.BENE_DEATH_DT <> ''
         THEN CAST(b.BENE_DEATH_DT AS INTEGER) END             AS death_dt,
    CAST(b.BENE_HI_CVRAGE_TOT_MONS  AS INTEGER)                AS part_a_mos,
    CAST(b.BENE_SMI_CVRAGE_TOT_MONS AS INTEGER)                AS part_b_mos,
    CAST(b.BENE_HMO_CVRAGE_TOT_MONS AS INTEGER)                AS hmo_mos,
    CAST(b.PLAN_CVRG_MOS_NUM        AS INTEGER)                AS part_d_mos,
    -- chronic condition warehouse flags: 1 = yes, 2 = no
    (b.SP_ALZHDMTA = '1') AS sp_alzhdmta, (b.SP_CHF = '1')      AS sp_chf,
    (b.SP_CHRNKIDN = '1') AS sp_chrnkidn, (b.SP_CNCR = '1')     AS sp_cncr,
    (b.SP_COPD = '1')     AS sp_copd,     (b.SP_DEPRESSN = '1') AS sp_depressn,
    (b.SP_DIABETES = '1') AS sp_diabetes, (b.SP_ISCHMCHT = '1') AS sp_ischmcht,
    (b.SP_OSTEOPRS = '1') AS sp_osteoprs, (b.SP_RA_OA = '1')    AS sp_ra_oa,
    (b.SP_STRKETIA = '1') AS sp_strketia,
    (b.SP_ALZHDMTA = '1') + (b.SP_CHF = '1') + (b.SP_CHRNKIDN = '1') + (b.SP_CNCR = '1') +
    (b.SP_COPD = '1') + (b.SP_DEPRESSN = '1') + (b.SP_DIABETES = '1') + (b.SP_ISCHMCHT = '1') +
    (b.SP_OSTEOPRS = '1') + (b.SP_RA_OA = '1') + (b.SP_STRKETIA = '1') AS n_chronic,
    -- annual amounts: Medicare reimbursement, beneficiary responsibility, primary payer
    CAST(b.MEDREIMB_IP  AS REAL) AS paid_ip,
    CAST(b.MEDREIMB_OP  AS REAL) AS paid_op,
    CAST(b.MEDREIMB_CAR AS REAL) AS paid_car,
    CAST(b.MEDREIMB_IP AS REAL) + CAST(b.MEDREIMB_OP AS REAL) + CAST(b.MEDREIMB_CAR AS REAL) AS paid_total,
    CAST(b.BENRES_IP AS REAL) + CAST(b.BENRES_OP AS REAL) + CAST(b.BENRES_CAR AS REAL)       AS benres_total,
    CAST(b.PPPYMT_IP AS REAL) + CAST(b.PPPYMT_OP AS REAL) + CAST(b.PPPYMT_CAR AS REAL)       AS pppymt_total
FROM stg_bene b;

CREATE INDEX ix_member_year ON member_year(bene_id, year);
