# 支氣管擴張症 · 門診一頁式儀錶板（離線版）

上傳門診紀錄 PDF → 自動擷取關鍵臨床參數 → 產生一頁式儀錶板（BSI / FACED / E-FACED
嚴重度評分、FEV₁ 趨勢、痰液微生物時間軸、用藥與臨床提示）。

**所有解析都在瀏覽器分頁內完成，沒有伺服器，沒有任何網路請求，沒有任何資料寫入硬碟。**

產出檔案：[`../bronchiectasis-dashboard.html`](../bronchiectasis-dashboard.html)（單一檔案，約 2.1 MB）

---

## 使用方式

1. 下載 `bronchiectasis-dashboard.html`
2. 雙擊開啟（`file://`，不需要伺服器、不需要安裝任何東西）
3. 拖入一份或多份門診 PDF（病歷、肺功能報告、微生物培養報告皆可）
4. 核對「評分輸入參數」表：`自動` 是機器擷取的，`待補` 請人工填入，任何欄位都能直接改，分數即時重算
5. 「列印 / 存成 PDF」輸出一頁式報告；「匯出去識別 JSON」給研究或統計用

支援多份 PDF 合併：上傳不同時間點的門診紀錄即可畫出 FEV₁ 趨勢與微生物時間軸。

---

## 資安設計

| 措施 | 實作 |
|---|---|
| 零外連 | 無 CDN、無外部字型、無 analytics。pdf.js 與中日韓字元對應表（cmaps）全部內嵌 |
| CSP 硬鎖 | `default-src 'none'; connect-src 'none'; worker-src 'none'; form-action 'none'; base-uri 'none'`，即使程式有瑕疵，瀏覽器也會擋掉一切對外連線 |
| 無 `unsafe-inline` | 建置時對每個 inline `<script>` / `<style>` 計算 SHA-256 寫進 CSP |
| 無 `unsafe-eval` | pdf.js 以 `isEvalSupported: false` 啟動 |
| 不落地 | 不使用 localStorage / IndexedDB / Cookie / Service Worker。PDF 以 `ArrayBuffer` 在記憶體中解析，關閉分頁即消失 |
| 無 blob worker | pdf.js 以主執行緒 fake-worker 模式運行，因此 `worker-src` 可以維持 `'none'`，在 `file://` 下也不會被瀏覽器阻擋 |
| XSS 防護 | 全程使用 `textContent` / `createElement`，完全不使用 `innerHTML`；病歷內容一律當成不可信輸入 |
| 去識別化 | 姓名 / 病歷號 / 身分證號預設遮蔽；匯出 JSON 一律移除識別欄位與原文片段 |
| 離開提醒 | 載入資料後關閉分頁會跳出確認，避免誤關 |
| 執行時自我驗證 | 頁面載入後顯示實際外部請求數（正常為 `0 個外部請求`） |

### 自行驗證（不要只相信說明）

```bash
# 1. 檔案內沒有任何外部 URL
grep -oE 'https?://[^"'"'"' )]+' bronchiectasis-dashboard.html | sort -u
#    只會出現註解與 CSP 內的字串，沒有被載入的資源

# 2. 記下雜湊值，日後可確認檔案未被替換
sha256sum bronchiectasis-dashboard.html
```

瀏覽器內：開 DevTools → Network → 勾 Preserve log → 上傳 PDF → 應只有一筆 `document`。
更硬的驗證：**整台電腦斷網**，功能應完全正常。

### 使用前的環境檢查

- 全碟加密已開啟（BitLocker / FileVault）
- 瀏覽器使用**無擴充套件**的獨立設定檔（擴充套件能讀取頁面 DOM，可繞過 CSP）
- 本檔案**不要**放在 OneDrive / iCloud / Google Drive 等自動同步目錄
- 依所屬機構規定確認個資、IRB 與資安政策

---

## 會擷取哪些欄位

| 類別 | 欄位 |
|---|---|
| 基本 | 姓名、病歷號、身分證號、性別、出生日期、年齡、就診日期（支援民國年） |
| 體位 | 身高、體重、BMI（缺 BMI 時由身高體重換算） |
| 肺功能 | FEV₁ (%pred, L)、FVC (%pred)、FEV₁/FVC |
| 症狀 | mMRC 呼吸困難分級、SpO₂、咳血、吸菸 pack-year |
| 病程 | 急性發作次數、住院紀錄、嚴重發作 |
| 微生物 | 綠膿桿菌、NTM、H. influenzae、MRSA、S. aureus、K. pneumoniae、Moraxella、Stenotrophomonas、Achromobacter、Burkholderia、Aspergillus、E. coli、Acinetobacter，以及「無細菌生長」 |
| 影像 | 支氣管擴張描述、侵犯肺葉（RUL/RML/RLL/LUL/LLL/Lingula）、囊狀 / 靜脈曲張型 / 柱狀、病因線索 |
| 用藥 | 長期 macrolide、吸入性抗生素、口服/靜脈抗生素、化痰藥、高張食鹽水、支氣管擴張劑、ICS、氣道清潔、疫苗 |

### 支援的病歷排版

1. **標籤:值同一行** — `姓名：王大明　病歷號：12345678`
2. **表格式（標題一行、值在下一行）** — 台灣多數 HIS 的門診紀錄匯出格式：

   ```
   姓名 身分證號 性別 出生日期 病歷號碼 門診日期 門診科別
   ooo  oooooooooo 女  1958-04-12 01234567 2026-09-24 胸腔內科
   ```

   偵測方式：一行中有 ≥3 個已知欄位標題且多數 token 都是標題 → 視為標題列，
   下一行 token 數相同時按欄位位置對應。欄數不合就不猜。

3. **SOAP 段落** — 自動辨識 `S:` `O:` `A:` `P:`，由 `A:` 段擷取診斷；
   `【TOCC…】` 問診區塊整段忽略，避免污染擷取結果。

日期支援：西元 `2026-09-24`、民國 `112/05/12`、`民國 42年03月18日`、無分隔 `20260828`。
身高體重支援 `BH:` / `BW:` 寫法，缺 BMI 時自動換算；缺年齡時由出生日期與就診日推算。

慢性定殖判定：同一菌種於 1 年內 ≥2 次陽性且間隔 ≥3 個月。

### 資料缺漏的處理原則（重要）

本工具**不會把「病歷沒提到」當成「沒有」**：

- 沒提到住院 → 標「待補」，不是 0 次（單一份門診紀錄不可能記載過去一年的住院史）
- 沒有培養報告 → 定殖標「待補」；只有在看到陰性培養報告時才判定為「無定殖」
- **任何一項缺漏，評分卡就不給嚴重度分級**，改顯示 `≥N` 下限並列出缺哪幾項

理由：缺漏的項目只會讓分數更高，若逕自當成 0 會算出假性偏低的嚴重度，
臨床上比「資料不足」危險得多。補齊參數後才會顯示輕／中／重度。

### 評分依據

- **BSI**（0–26）：Chalmers et al., *Am J Respir Crit Care Med* 2014。輕度 0–4 / 中度 5–8 / 重度 ≥9。
  注意 BSI 原始量表使用 **MRC 1–5**，本工具輸入 mMRC 0–4，換算時自動 +1。
- **FACED**（0–7）：Martínez-García et al., *Eur Respir J* 2014。輕度 0–2 / 中度 3–4 / 重度 5–7。
- **E-FACED**（0–9）：Martínez-García et al., *COPD* 2017。輕度 0–3 / 中度 4–6 / 重度 7–9。

臨床提示參考 ERS 2017 與 BTS 2019 支氣管擴張症指引的一般原則。
**請依所屬機構採用的版本核對截切點。**

---

## 已知限制

- **掃描影像 PDF 無法解析**。本工具只讀取 PDF 內嵌的文字圖層；掃描件需要 OCR，
  為了控制檔案大小與攻擊面，目前未內建 OCR。遇到時頁面會跳出橙色橫幅說明原因與確認方法，
  並提供「改用手動輸入模式」開啟空白表單，仍可手動填入參數並算出評分與列印。
- **診斷面板**：每次載入後可在「原始擷取文字」看到 pdf.js 實際抽到的每一行（含頁碼），
  用來區分「PDF 讀不到文字」與「讀到文字但規則沒對上」。
- **規則式擷取會出錯**。中文病歷格式差異極大，自動擷取只是省去打字，
  每個數值都附「來源追溯」（第幾頁、哪一行原文），**臨床決策前請逐項核對**。
- 擷取不到的欄位標示為 `待補`，評分卡會顯示「資料不足」而不是給出一個看似有效的分數。
- 不做 NLP 否定偵測，例如「無綠膿桿菌生長」以外的複雜否定句可能誤判為陽性。
- 本工具僅供臨床參考，不取代專業判斷。

---

## 建置

```bash
python3 bronchiectasis/build.py     # → bronchiectasis-dashboard.html
```

建置腳本會：內嵌 pdf.js 與 cmaps → 計算 CSP 雜湊 → **檢查產出檔內是否有任何外部資源參照，有就建置失敗**。

### 端對端測試（含零外連驗證）

```bash
cd bronchiectasis/test
npm install playwright
node e2e.js
```

測試會產生模擬中文門診 PDF、在真實 Chromium 中載入儀錶板、驗證擷取結果與評分，
並斷言 **非 `file://` 的網路請求數為 0、console 錯誤數為 0**。

---

## 授權與致謝

- 本工具程式碼：與本 repo 相同授權
- [pdf.js](https://github.com/mozilla/pdf.js) v3.11.174（Mozilla，Apache-2.0）— 見 `vendor/LICENSE-pdfjs`
