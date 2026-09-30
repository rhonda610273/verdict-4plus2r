# 資料字典

> 這份文件由 `tools/gen_datadict.py` 從 `fields.py` 自動產生，請勿手動編輯。
> 修改欄位請改 `fields.py`，然後重新執行該腳本。

欄位設計參考 ATS/IDSA/ERS/ESCMID 2020 年 NTM 肺病治療指引，
以及常見的 NTM 世代研究登錄項目。實際使用時請依科內需求增刪。

## 系統自動產生的欄位

| 欄位 | 說明 |
|---|---|
| `id` | 內部流水號 |
| `ats_met` | 三項 ATS/IDSA 條件是否皆符合（由臨床／影像／微生物三個勾選欄位計算） |
| `age_at_dx` | 確診年齡 = 確診日期年份 − 出生年 |
| `treatment_months` | 療程月數 = (治療結束日 − 治療開始日) / 30.44 |
| `created_at` / `created_by` | 建檔時間與建檔者 |
| `updated_at` / `updated_by` | 最後修改時間與修改者 |
| `deleted` | 軟刪除旗標，刪除的個案不會真的消失 |

## 登錄欄位


### 其他

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `study_id` | Study ID | 文字 |  |
| `observe_or_treat_group` | 組別 | 單選 | 觀察組、治療組 |
| `patient_code` | 病人編號 | 文字 | ＊去識別化編號，格式 組別-醫院碼-年月-個案序（例 T-001-2410-001）<br>**必填** |

### Consent Information

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `hospital_site` | 收案醫院 | 單選 | 北榮、部桃、台大、新竹台大、雲林台大、輔大、中榮、高榮、高醫、成大、花慈、林長、高長、中國醫、中山醫、彰基、萬芳、部台中 |
| `date_enrolled` | 簽署同意書日期 | 日期 | ＊YYYY-MM-DD |
| `dob` | 出生日期 | 日期 |  |
| `age` | 年齡 | 小數 |  |
| `sex` | 性別 | 單選 | Female、Male |
| `height` | 身高 (cm) | 小數 |  |
| `weight` | 體重 (kg) | 整數 |  |
| `bmi` | BMI | 小數 |  |

### smoking_hx

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `smoke` | 吸菸史 | 單選 | Never、active smoker、former smoker |
| `pack_perday` | pack_perday | 文字 |  |
| `smoke_duration` | smoke_duration | 文字 |  |
| `quit_duration` | quit_duration | 文字 |  |

### Exposure_hx

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `shower_with_handheld_showerhead` | 幾乎每日使用蓮蓬頭沖澡 | 是/否 |  |
| `regular_water_activities` | 水療/泡溫泉 | 是/否 |  |
| `water_activity_frequency` | 水療/泡溫泉_頻率 | 複選 | 每週1-3次、每月1-3次、每季1-3次 |
| `gardening_activities_moth` | 園藝或土壤接觸之活動 | 是/否 |  |
| `gardening_activity_month` | 園藝或土壤接觸之活動頻率 | 複選 | 幾乎每日有、每週1-3次,、每月1-3次,、每季1-3次 |
| `ntm_exposure_resident` | 同住是否有人同樣被診斷出有NTM肺病 | 單選 | 是、否 |
| `ntm_exposure_resident_year` | ntm_exposure_resident_year | 單選 | 過去3年內有,、>3年之前曾有 |
| `ntm_exposure_work` | 同住是否有人同樣被診斷出有NTM肺病 | 單選 | 是、否 |
| `ntm_exposure_work_year` | ntm_exposure_work_year | 單選 | 過去3年內有,、>3年之前曾有 |
| `past_tb_treatment` | 過去曾經接受過結核病治療嗎 | 是/否 |  |
| `start_tb_day` | 接受結核菌藥物治療時間 | 日期 |  |
| `ntmpd_treatment` | 過去曾經接受過NTM肺病治療嗎 | 是/否 |  |
| `start_ntmtx_day` | 接受NTM藥物治療時間 | 日期 |  |

### Comorbidity

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `type2_dm` | 糖尿病 | 是/否 |  |
| `ckd` | 慢性腎衰竭 | 是/否 |  |
| `liver_cirrhosis` | 肝硬化 | 是/否 |  |
| `hbv` | 活動性B型肝炎 | 是/否 |  |
| `hcv` | 活動性C型肝炎 | 是/否 |  |
| `gerd` | 胃食道逆流 | 是/否 |  |
| `copd` | 慢性阻塞性肺病 | 是/否 |  |
| `asthma` | 氣喘 | 是/否 |  |
| `bronchiectasis` | 支氣管擴張 | 是/否 |  |
| `old_tb` | 陳舊性肺結核 | 是/否 |  |
| `pneumoconiosis` | 塵肺症 | 是/否 |  |
| `ntm_hx` | 非結核分枝桿菌肺病史 | 是/否 |  |
| `ild` | 間質性肺病 | 是/否 |  |
| `ra` | 類風濕關節炎 | 是/否 |  |
| `sle` | 紅斑性狼瘡 | 是/否 |  |
| `sacoidosis` | 類肉瘤 | 是/否 |  |
| `other_autoimmune` | 其他自體免疫疾病 | 文字 |  |
| `cancer` | 惡性腫瘤 | 是/否 |  |
| `cancer_site` | 惡性腫瘤部位 | 文字 |  |
| `cancer_status` | 惡性腫瘤目前狀態 | 單選 | stable、active |
| `immunotherapy_cancer` | 使用免疫治療 | 單選 | 過去使用免疫治療,、現在使用免疫治療 |
| `pneumonia_admission_hx` | 診斷日前兩年是否有肺炎住院記錄 | 是/否 |  |
| `tracheostomy_hx` | 前兩年是否有氣切管使用 | 是/否 |  |

### 過去半年有接受下列藥物治療

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `ocs_use` | 口服類固醇 | 單選 | 無、有 |
| `longterm_ocs` | prednisolone 10mg/day >3週 | 單選 | 無、有 |
| `ics` | 吸入類固醇 | 單選 | 無、有 |
| `chemo` | 化學治療 | 單選 | 無、有 |
| `antitnf` | 抗腫瘤壞死因子 | 單選 | 無、有 |
| `immunosuppresion` | 免疫抑制藥物 | 單選 | 無、有 |

### 臨床症狀

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `fever` | 發燒 | 是/否 |  |
| `fatigue` | 疲倦 | 是/否 |  |
| `poor_appetite` | 食慾不振 | 是/否 |  |
| `bw_loss` | 體重減輕 | 是/否 |  |
| `bw_loss_month` | _________個月內減輕 | 文字 |  |
| `be_loss_kg` | 減輕幾公斤 | 文字 |  |

### Respiratory Symptoms Score(RSS)

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `cough_rss` | 咳嗽 (RSS) | 單選 | 0、1、2、3、4、5、6、7、8、9、10 |
| `dyspnea_rss` | 喘 (RSS) | 單選 | 0、1、2、3、4、5、6、7、8、9、10 |
| `phlegm_rss` | 痰 (RSS) | 單選 | 0、1、2、3、4、5、6、7、8、9、10 |
| `hemoptysis_rss` | 咳血 (RSS) | 單選 | 0、1、2、3、4、5、6、7、8、9、10 |
| `chesttightness_rss` | 胸悶 (RSS) | 單選 | 0、1、2、3、4、5、6、7、8、9、10 |
| `sleepdistrubance_rss` | 睡眠中斷 (RSS) | 單選 | 0、1、2、3、4、5、6、7、8、9、10 |
| `total_rss_score` | RSS 總分 | 小數 |  |
| `mmrc` | mMRC 分數 | 文字 |  |

### NTM肺病首次 診斷資料,微生物學診斷依據

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `ntm_species` | 主要致病菌 | 複選 | M.avium Complex (MAC)、M.abscessus (MAB)、M.kansasii、M.fortuitum、其他<br>＊單選 |
| `ntm_species_other` | 主要致病菌其他(單選) | 文字 |  |
| `ntm_diagnosis_microbiology` | 微生物學診斷依據 | 複選 | 痰液培養(≥2套)、BAL/wash 培養(≥1套)、肺切片典型變化+培養(1套切片、痰或BAL/wash) |
| `afs_initial` | 痰液抗酸染色抹片 | 單選 | 陰性、陽性、未驗 |
| `afs_titer_initial` | 抺片陽性之最高價數 | 單選 | trace、1+、2+、3+、4+、0 |
| `ntm_sputumculture_initial` | 痰液分枝桿菌培養 | 單選 | 陰性、陽性、未驗 |
| `ntm_sputum_culture_species` | 痰液分枝桿菌分型鑑定結果 | 單選 | MAC、MABC、M.kansasii、M. fortuitum、其他 |
| `ntm_sputum_culture_others` | 痰液其他分枝桿菌分型鑑定結果 | 文字 |  |
| `ntm_positive_day` | 首次痰培養陽性日期 | 日期 |  |
| `ntm_positive_sample` | 陽性套數 | 文字 |  |
| `ntm_sample_total` | 總共送幾套 | 文字 |  |
| `ntm_balculture_initial` | BAL分枝桿菌培養 | 單選 | 陰性、陽性、未驗 |
| `ntm_bal_culture_species` | BAL分枝桿菌分型鑑定結果 | 單選 | MAC、MABC、M.kansasii、M. fortuitum |
| `ntm_bal_culture_others` | BAL其他分枝桿菌分型鑑定結果 | 文字 |  |
| `ntm_tissueculture_initial` | 肺部切片分枝桿菌培養 | 單選 | 陰性、陽性、未驗 |
| `ntm_tissue_culture_species` | 肺切片分枝桿菌分型鑑定結果 | 單選 | MAC、MABC、M.kansasii、M. fortuitum |
| `ntm_tissue_culture_others` | 肺切片其他分枝桿菌分型鑑定結果 | 文字 |  |
| `ntm_type_method` | 分枝桿菌分型鑑定方法 | 單選 | MALDI-TOF mass spectrometry、Genotyping(晶宇)、inhouse PCR |

### NTM肺病首次診斷影像

| 欄位名稱 | 標籤 | 型別 | 選項 / 說明 |
|---|---|---|---|
| `cxr_dignosis_time` | 診斷時CXR 發現 | 日期 |  |
| `cxr_radiolographic_socre` | CXR之radiographic score (0-18) | 文字 | ＊Brixia ScoreEach zone is scoring as: Score 0 no lung abnormalities, Score 1 interstitial infiltrates, Score 2 interstit |
| `ct_diagnosis_time` | 胸部電腦斷層 (一年內的) | 日期 |  |
| `ct_imagepattern` | 胸部電腦斷層影像型態 | 複選 | FC,Fibrocavitary、Cavitary NB, Cavitary Nodular Bronchiectasis、Non-cavitary NB, Non-cavitary Nodular Bronchiectasis、consolidative change,、cystic lesion,、mass（＞３cm）、nodule (1-3cm)、multiple nodule,、tree-in-bud pattern、diffuse fibrosis、Bilateral lung disease |
| `combined_infection` | 合併其他感染: | 複選 | Pseudomonas、KP,Klebsiella pneumoniae、H inf. Haemophilus influenzae、Staphy. Staphylococcus aureus、Aspergillus; |
| `combined_infection_2` | 合併其他感染 Other GNB: | 文字 |  |
| `ast` | AST | 文字 |  |
| `alt` | ALT | 文字 |  |
| `t_bil` | T.Bililrubin | 文字 |  |
| `bun` | BUN | 文字 |  |
| `cre` | Cre | 文字 |  |
| `albumin` | Albumin | 文字 |  |
| `hbsag` | HBsAg | 單選 | +、- |
| `hcv_ab` | HCV-Ab | 單選 | +、- |
| `wbc` | WBC | 文字 |  |
| `neutrophil` | Neutrophil% | 文字 |  |
| `lym` | Lym％ | 文字 |  |
| `eos` | Eos％ | 文字 |  |
| `monocyte` | Monocyte％ | 文字 |  |
| `hb` | Hb | 文字 |  |
| `plt` | Plt | 文字 |  |
| `esr` | ESR | 文字 |  |
| `crp` | CRP mg/dl | 文字 |  |
| `ca_125` | CA-125 | 文字 |  |
| `ca_199` | CA-199 | 文字 |  |
| `aspergillus_fumigatus_igg` | Aspergillus fumigatus IgG | 文字 |  |
| `a_niger_igg` | Aspergillus niger IgG | 文字 |  |
| `pft_day` | 診斷前後6個月內(治療前)的肺功能檢查 (日期 ____/____/____) | 日期 |  |
| `prefev1` | FEV1: pre-BD (L) | 文字 |  |
| `prefev1pred` | FEV1: pre-BD %PRED | 文字 |  |
| `prefvc` | FVC: pre-BD (L) | 文字 |  |
| `prefvcpred` | FVC preBD %pred | 文字 |  |
| `prefev1fvc` | FEV1/FVC: pre-BD % | 文字 |  |
| `postfev1` | FEV1: post-BD (L) | 文字 |  |
| `postfev1pred` | FEV1: post-BD %PRED | 文字 |  |
| `postfvc` | FVC: post-BD (L) | 文字 |  |
| `postfvcpred` | FVC postBD %pred | 文字 |  |
| `postfev1fvc` | FEV1/FVC: post-BD % | 文字 |  |
| `start_treatment` | 收案時是否啟動治療 | 是/否 |  |
| `start_treatment_reason` | 啟動治療的原因 | 單選 | 症狀太嚴重、症狀追蹤時加重、菌量太嚴重、菌量追蹤時變多、影像太嚴重、影像追蹤時變化、病患免疫不全,有治療需求、可追蹤但病人要求治療 |
| `start_tx_symptom` | 啟動治療原因:症狀追蹤時加重 | 複選 | 咳嗽、喘、痰、咳血、體重減輕、盜汗、發燒 |
| `start_tx_afs` | 菌量太嚴重 | 複選 | 抺片陽性,、抹片≥ 3+ |
| `start_tx_followup_afs` | 菌量追蹤時變多 | 複選 | 抺片陰轉陽、培養2套變3套 |
| `start_tx_image` | 影像太嚴重 | 複選 | 開洞、雙側、多葉 |
| `start_tx_followup_image` | 影像追蹤時變化 | 複選 | 新開洞,、範圍變大 |
| `antimac_time` | Anti-MAC起始日 | 日期 |  |
| `antimac_regimen` | Anti-MAC regimen | 複選 | Azithromycin,、Clarithromycin、EMB、RIF、Rbt、INH、IV Amikacin、IH Amikacin、Linezolid、Moxifloxacin、Levofloxacin、Co-trimoxazole、Minocycline、Doxycycline |
| `antimac_regimen_other` | Anti-MAC Regimen other | 文字 |  |
| `antimac_ihamikin_time` | antiMAC IH Amikacin使用幾周 | 文字 |  |
| `anti_mk` | Anti-MK | 日期 |  |
| `antimk_regimen` | Anti-MK regimen | 複選 | Azithromycin,、Clarithromycin、EMB、RIF、Rbt、INH、IV Amikacin、IH Amikacin、Linezolid、Moxifloxacin、Levofloxacin、Co-trimoxazole、Minocycline、Doxycycline |
| `antimk_regimen_other` | Anti-MK Regimen other | 文字 |  |
| `antimk_ihamikin_time` | antiMK IH Amikacin使用幾周 | 文字 |  |
| `anti_mabs_initial_phase_time` | Anti-Mabs regimen Initial phase 開始時間 | 日期 |  |
| `anti_mabs_initial_phase_closetime` | Anti-Mabs regimen Initial phase 結束時間 | 日期 |  |
| `anti_mabs_consolidation_time` | Anti-Mabs regimen 持續期 | 日期 |  |
| `anti_mabs_initial_regimen` | Anti-Mabs Initial phase regimen | 複選 | Azithromycin、Clarithromycin、Amikacin、Imipenem、Cefoxitin、Tigecycline |
| `anti_mabs_continu_regimen` | Anti-Mabs Continuous regimen | 複選 | Azithromycin、Clarithromycin、Linezolid、Moxifloxacin、Levofloxacin、Rbt、Co-trimoxazole、Minocycline、Doxycycline、IH Amikacin |
| `amikin_neunulizer` | IH Amikacin 使用的neubulizer | 複選 | Jet nebulizer、Mesh、Ultrasonic |
| `ntm` | 其他分型ntm治療起始時間 | 日期 |  |
| `ntm_other_tx` | 其他NTM分型治療 | 複選 | Azithromycin,、Clarithromycin、EMB、RIF、Rbt、INH、IV Amikacin、IH Amikacin、Linezolid、Moxifloxacin、Levofloxacin、Co-trimoxazole、Minocycline、Doxycycline |

---

## 定義註記

填寫前建議先在科內統一以下定義，並寫進填寫規範：

* **確診日期** — 建議採「第一次同時滿足 ATS/IDSA 臨床、影像、微生物三項條件」的日期。
* **微生物條件** — ATS/IDSA 標準為：≥2 套分開採檢的痰液培養陽性，或 1 套支氣管沖洗液／
  BAL 培養陽性，或肺組織切片有分枝桿菌組織學特徵且培養陽性。
* **培養轉陰** — 本系統採「連續 ≥3 次培養陰性」，日期記錄第一次陰性的採檢日。
* **持續轉陰 12 個月** — 轉陰後持續陰性滿 12 個月，且療程結束時仍為陰性。
* **復發 vs. 再感染** — 需菌株基因型比對才能區分；無法比對時請填「不詳」。
* **M. abscessus 的 erm(41)** — 功能型會造成誘導型 macrolide 抗藥，影響處方選擇，
  建議常規記錄。

## 匯出

網頁上「匯出 CSV」會輸出所有登錄欄位加上系統自動欄位。
複選欄位以分號 `;` 分隔，是/否欄位輸出「是」／「否」，檔案帶 UTF-8 BOM，
Excel 直接打開不會亂碼，也可直接用 R 的 `read.csv(..., fileEncoding="UTF-8-BOM")` 讀入。

