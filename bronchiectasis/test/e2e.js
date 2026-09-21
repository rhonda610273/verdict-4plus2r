const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUT = path.join(__dirname, 'fixtures');
const APP = path.resolve(__dirname, '..', '..', 'bronchiectasis-dashboard.html');
const CHROME = process.env.CHROME_PATH || undefined;

const CSS = `body{font-family:'WenQuanYi Zen Hei',sans-serif;font-size:12px;line-height:1.7;padding:18px}
h2{font-size:14px;margin:10px 0 4px}pre{font-family:inherit;white-space:pre-wrap;margin:0}`;

const DOCS = [
  ['visit-2023-05.pdf', `台大醫院 胸腔內科 門診紀錄
姓名：王大明    病歷號：12345678    身分證號：A123456789
性別：男    出生日期：民國 42年03月18日    年齡：70 歲
就診日期：112/05/12
身高：168 cm    體重：50.2 kg    BMI：17.8

主訴：慢性咳嗽合併大量膿痰三年
現病史：已知支氣管擴張症。過去一年急性發作 3 次，其中一次因肺炎住院治療 7 天。
mMRC 呼吸困難分級：2
理學檢查：SpO2 94 %，雙下肺可聞及爆裂音
抽菸史：20 pack-year，已戒菸 10 年

肺功能檢查 (2023/05/10)
FVC        2.35 L      68 % pred
FEV1       1.28 L      52 % pred
FEV1/FVC   54 %

胸部電腦斷層 (2022/11/03)：
兩側支氣管擴張，以 RLL、LLL 及 Lingula 為主，部分呈囊狀 (cystic) 變化。
推測為結核後 (post-infectious) 變化。

痰液培養 (2023/05/10)：Pseudomonas aeruginosa (3+)

處方：
Azithromycin 250 mg QOD
N-acetylcysteine 600 mg BID
Tiotropium inhaler QD
衛教：胸腔物理治療與姿位引流，每日兩次`],

  ['visit-2023-11.pdf', `台大醫院 胸腔內科 門診紀錄
姓名：王大明    病歷號：12345678
就診日期：112/11/20
體重：49.5 kg
mMRC：2

肺功能檢查 (2023/11/18)
FEV1  1.18 L   48 % pred
FVC   2.28 L   66 % pred

痰液培養 (2023/11/18)：Pseudomonas aeruginosa
處方：Azithromycin 250 mg QOD、Colistin 吸入型抗生素 BID`],

  ['culture-2024-04.pdf', `微生物檢驗報告
姓名：王大明    病歷號：12345678
採檢日期：113/04/08
檢體種類：痰液 (Sputum)
培養結果：
  Pseudomonas aeruginosa
  Haemophilus influenzae
抗生素敏感性試驗：見附頁`],
];

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch(CHROME ? { executablePath: CHROME } : {});

  // ── 1. 產生模擬門診 PDF ──────────────────────────────────────
  const gen = await browser.newPage();
  for (const [name, body] of DOCS) {
    await gen.setContent(`<!DOCTYPE html><meta charset="utf-8"><style>${CSS}</style><pre>${body}</pre>`);
    await gen.pdf({ path: path.join(OUT, name), format: 'A4', printBackground: true });
  }
  await gen.close();
  console.log('✓ 產生 ' + DOCS.length + ' 份測試 PDF');

  // ── 2. 載入儀錶板並監控所有網路活動 ──────────────────────────
  const ctx = await browser.newContext();
  const requests = [];
  ctx.on('request', r => { if (!r.url().startsWith('file://')) requests.push(r.url()); });
  const page = await ctx.newPage();
  const consoleErrs = [];
  page.on('console', m => { if (m.type() === 'error') consoleErrs.push(m.text()); });
  page.on('pageerror', e => consoleErrs.push('PAGEERROR: ' + e.message));

  await page.goto('file://' + APP);
  await page.setInputFiles('#file', DOCS.map(d => path.join(OUT, d[0])));
  await page.waitForFunction(() => !document.getElementById('dash').hidden, { timeout: 60000 });
  await page.waitForTimeout(600);

  // ── 3. 讀取結果 ──────────────────────────────────────────────
  const res = await page.evaluate(() => {
    const t = id => (document.getElementById(id) || {}).textContent;
    const S = window.__BE__.STATE;
    const params = {};
    for (const k in S.params) params[k] = S.params[k].value;
    return {
      pill: t('netPill'),
      bsi: t('bsiN'), bsiSev: t('bsiSev'),
      faced: t('facedN'), facedSev: t('facedSev'),
      efaced: t('efacedN'), efacedSev: t('efacedSev'),
      params,
      docs: S.docs.length,
      orgs: S.docs.reduce((a, d) => a + d.organisms.length, 0),
      chips: Array.from(document.querySelectorAll('#microChips .chip')).map(c => c.textContent),
      meds: Array.from(document.querySelectorAll('#meds .chip')).map(c => c.textContent),
      findings: Array.from(document.querySelectorAll('#findings .chip')).map(c => c.textContent),
      flags: Array.from(document.querySelectorAll('#flags .flag .tx b')).map(c => c.textContent),
      fevPts: (document.querySelectorAll('#fevChart svg circle') || []).length,
      microPts: (document.querySelectorAll('#microChart svg circle') || []).length,
      log: Array.from(document.querySelectorAll('#log div')).map(d => d.textContent),
      demo: Array.from(document.querySelectorAll('#demoTbl tr')).map(
        r => r.children[0].textContent + ' = ' + r.children[1].textContent),
    };
  });

  console.log('\n──────── 解析結果 ────────');
  res.log.forEach(l => console.log('  ' + l));
  console.log('\n  零外連指示： ' + res.pill);
  console.log('  BSI    : ' + res.bsi + '  ' + res.bsiSev);
  console.log('  FACED  : ' + res.faced + '  ' + res.facedSev);
  console.log('  E-FACED: ' + res.efaced + '  ' + res.efacedSev);
  console.log('\n  參數: ' + JSON.stringify(res.params));
  console.log('  病人摘要:'); res.demo.forEach(d => console.log('    ' + d));
  console.log('  微生物 (' + res.orgs + ' 筆): ' + res.chips.join(' | '));
  console.log('  用藥: ' + res.meds.join(' | '));
  console.log('  發現: ' + res.findings.join(' | '));
  console.log('  FEV1 點數: ' + res.fevPts + ' / 微生物時間軸點數: ' + res.microPts);
  console.log('  提示:'); res.flags.forEach(f => console.log('    - ' + f));

  console.log('\n──────── 資安驗證 ────────');
  console.log('  非 file:// 網路請求數: ' + requests.length + (requests.length ? ' → ' + requests.join(', ') : ' ✓'));
  console.log('  console 錯誤數: ' + consoleErrs.length);
  consoleErrs.slice(0, 12).forEach(e => console.log('    ! ' + e.slice(0, 220)));

  // ── 4. 測試手動覆寫會重算 ────────────────────────────────────
  const before = res.bsi;
  await page.evaluate(() => {
    const B = window.__BE__;
    B.STATE.params.mmrc = { value: 4, src: null, manual: true };
    B.refresh();
  });
  const after = await page.evaluate(() => document.getElementById('bsiN').textContent);
  console.log('\n  手動覆寫 mMRC 2→4：BSI ' + before + ' → ' + after +
              (Number(after) === Number(before) + 3 ? "  ✓ 重算正確 (mMRC4→MRC5 = +3)" : '  ✗ 未如預期'));

  // ── 5. 列印版面 ──────────────────────────────────────────────
  await page.emulateMedia({ media: 'print' });
  await page.pdf({ path: path.join(OUT, 'dashboard-print.pdf'), format: 'A4', printBackground: true });
  const printPages = fs.statSync(path.join(OUT, 'dashboard-print.pdf')).size;
  console.log('  列印輸出已產生 (' + Math.round(printPages / 1024) + ' KB)');

  await browser.close();

  const fail = requests.length > 0 || consoleErrs.length > 0;
  console.log('\n' + (fail ? '✗ 測試失敗（見上方）' : '✓ 全部通過'));
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('TEST FAILED:', e); process.exit(1); });
