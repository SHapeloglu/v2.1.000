/**
 * main.js — MailSender Pro İstemci Tarafı JavaScript
 * =====================================================
 * Tüm sayfa etkileşimleri, API çağrıları ve UI mantığı burada toplanmıştır.
 *
 * BÖLÜMLER:
 *   1. Yardımcı fonksiyonlar  — togglePw, showAlert, esc, setSPort, vb.
 *   2. DB işlemleri           — loadDbConfig, genKey, testDb, saveDb
 *   3. Gönderici yönetimi     — loadSenders, editSenderFn, saveSender, testSender, delSender
 *   4. Kural yönetimi         — loadRules, editRuleFn, saveRule, delRule
 *   5. Tek gönderim           — sendSingle
 *   6. Toplu gönderim         — startBulk, startBulkFromDb, handleBulkEvent
 *   7. Excel işlemleri        — previewExcel, promptExcelImport, confirmImport
 *   8. Değişken etiketleri    — updateVarTags, insertVar
 *   9. Log görüntüleme        — loadLog
 *  10. EC2 yönetimi           — manualStopEc2
 *  11. Global atamalar        — window.* (inline onclick için)
 *
 * ÖNEMLİ KAVRAMLAR:
 *   - SSE (Server-Sent Events): sunucudan tek yönlü canlı veri akışı
 *     Okuma: ReadableStream + TextDecoder ile satır satır parse edilir
 *   - AbortController: aktif SSE stream'ini iptal etmek için kullanılır
 *   - window._bulkStopped: "Durdur" butonuna basıldığını stream döngüsüne bildirir
 *   - activeTarget: {{değişken}} etiketinin hangi alana (konu/mesaj) ekleneceğini tutar
 */


// ── API Servis Adı Tespiti ─────────────────────────────────────────
/**
 * API gönderici host adresine bakarak bilinen servis adını ve etiketini döner.
 * Gönderim logu ve seçim listelerinde kullanıcı dostu isimler göstermek için kullanılır.
 * Tanınmayan hostlar için host adının ilk parçası kullanılır.
 * @param {string} host - api_host değeri (örn: "api.mailrelay.com")
 * @returns {{label: string, short: string}}
 */
function detectApiService(host) {
    if (!host) return {label: '🔌 API', short: 'API'};
    const h = host.toLowerCase();
    if (h.includes('mailrelay') || h.includes('ipzmarketing')) return {label: '📮 Mailrelay', short: 'Mailrelay'};
    if (h.includes('brevo') || h.includes('sendinblue'))      return {label: '💙 Brevo',     short: 'Brevo'};
    if (h.includes('sendgrid'))  return {label: '✉ SendGrid',  short: 'SendGrid'};
    if (h.includes('postmark'))  return {label: '📬 Postmark',  short: 'Postmark'};
    if (h.includes('resend'))    return {label: '⚡ Resend',    short: 'Resend'};
    if (h.includes('mailgun'))   return {label: '🔫 Mailgun',   short: 'Mailgun'};
    if (h.includes('sparkpost')) return {label: '✨ SparkPost', short: 'SparkPost'};
    if (h.includes('amazon') || h.includes('amazonaws')) return {label: '☁ SES',     short: 'SES'};
    return {label: '🔌 ' + host.replace(/^api\./, '').split('.')[0], short: host.split('.')[0]};
}
// ── Global Durum Değişkenleri ────────────────────────────────────────
let editSenderId   = null;        // Düzenleme modunda olan gönderici ID'si (null = yeni ekleme modu)
let editRuleId     = null;        // Düzenleme modunda olan kural ID'si
let logPage        = 1;           // Şu an görüntülenen log sayfası numarası
let activeTarget   = 'b-body';    // {{değişken}} etiketinin ekleneceği alan: 'b-body' | 'b-subject'
let listSource     = 'db';        // Toplu gönderim kaynağı: 'db' | 'excel' | 'paste'
let currentExcelFile = null;      // Import modalında bekleyen Excel File objesi
let currentDfColumns = [];        // Import modalında gösterilen sütun listesi
let importAction   = 'new';       // Excel aktarım modu: 'new' | 'overwrite' | 'append' | 'append_dedupe'

// ── Yardımcı Fonksiyonlar ────────────────────────────────────────────

/** Şifre alanını gizle/göster arasında geçiş yapar. btn: göz ikonu butonu */
function togglePw(id, btn) {
    const i = document.getElementById(id);
    i.type = i.type === 'password' ? 'text' : 'password';
    btn.textContent = i.type === 'password' ? '👁' : '🙈';
}

/** Dosya seçildiğinde adını ilgili span'e yazar (tid: hedef element ID) */
function showFn(inp, tid) {
    document.getElementById(tid).textContent = inp.files[0] ? '📎 ' + inp.files[0].name : '';
}

/**
 * Alert kutusu gösterir.
 * @param {string} id   - Alert element ID'si
 * @param {string} msg  - Gösterilecek mesaj
 * @param {string} type - CSS sınıfı: 'ok' (yeşil) | 'err' (kırmızı) | 'warn' (sarı)
 */
function showAlert(id, msg, type) {
    const el = document.getElementById(id);
    el.textContent = msg;
    el.className = 'alert ' + type + ' show';  // 'show' görünür kılar
}

/** Alert kutusunu gizler (sınıfı sıfırlar) */
function hideAlert(id) {
    document.getElementById(id).className = 'alert';
}

/**
 * HTML özel karakterlerini escape eder (XSS koruması).
 * innerHTML ile dinamik içerik oluştururken mutlaka kullanılmalı.
 */
function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * SMTP port hızlı seçim butonu (465 / 587 / 25).
 * Seçilen porta karşılık gelen pill butonunu aktif yapar.
 */
function setSPort(v, btn) {
    const portEl = document.getElementById('s-port');
    if (portEl) portEl.value = v;
    // Aynı pill grubundaki diğer butonlardan 'active' sınıfını kaldır
    const container = btn.closest('.pills');
    if (container) container.querySelectorAll('.pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
}

/**
 * Gönderim aralığı hızlı seçim butonu (0 / 24 / 48 / 168 saat).
 * Değeri r-interval input'una yazar ve önizlemeyi günceller.
 */
function setRInterval(v, btn) {
    const el = document.getElementById('r-interval');
    if (el) el.value = v;
    updateIPreview();  // "X saat arayla" metnini güncelle
    const container = btn.closest('.pills');
    if (container) container.querySelectorAll('.pill').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
}

/**
 * Saat değerini okunabilir metne çevirir ve ip-val element'ine yazar.
 * 0 → sınırsız | <24 → saat | <168 → gün | ≥168 → hafta
 */
function updateIPreview() {
    const v = parseInt(document.getElementById('r-interval').value) || 0;
    const el = document.getElementById('ip-val');
    if (v === 0)        el.textContent = 'sınırsız sıklıkta';
    else if (v < 24)   el.textContent = v + ' saat arayla';
    else if (v < 168)  el.textContent = Math.round(v / 24) + ' gün arayla';
    else               el.textContent = Math.round(v / 168) + ' hafta arayla';
}

/**
 * Toplu gönderim sayfasında kural seçildiğinde çalışır.
 * Seçilen kuralın aralık bilgisini (rule-info paneli) gösterir/gizler.
 * data-interval: <option> element'inin HTML data attribute'u.
 */
function onRuleChange() {
    const sel = document.getElementById('b-rule');
    const opt = sel.options[sel.selectedIndex];
    const h   = opt.dataset.interval;       // option'ın data-interval değeri
    const ri  = document.getElementById('rule-info');
    if (!sel.value) { ri.style.display = 'none'; return; }
    ri.style.display = 'flex';
    document.getElementById('ri-val').textContent = h == '0' ? 'sınırsız' : h + ' saat';
}

// ── DB İşlemleri ─────────────────────────────────────────────────────

/** Mevcut DB ayarlarını sunucudan çekip form alanlarına doldurur.
 *  SECRET_KEY varsa placeholder 'Mevcut anahtar korunuyor...' olur (değer gösterilmez). */
async function loadDbConfig() {
    try {
        const d = await (await fetch('/api/db-config')).json();
        const h = document.getElementById('db-host');
        const p = document.getElementById('db-port');
        const u = document.getElementById('db-user');
        const n = document.getElementById('db-name');
        if (h) h.value = d.DB_HOST || '';
        if (p) p.value = d.DB_PORT || '3306';
        if (u) u.value = d.DB_USER || '';
        if (n) n.value = d.DB_NAME || '';
        const skEl = document.getElementById('sk');
        if (skEl && d.HAS_SECRET_KEY) {
            skEl.placeholder = 'Mevcut anahtar korunuyor...';
        }
    } catch (e) { }
}

/**
 * Tarayıcı Crypto API ile 32 bayt rastgele veri üretir, base64url formatına çevirir.
 * Bu format Fernet anahtarı için uygundur (44 karakter, URL güvenli).
 * Üretilen anahtar sk input'una yazılır ve görünür yapılır.
 */
function genKey() {
    const a = new Uint8Array(32);
    crypto.getRandomValues(a);  // Kriptografik olarak güvenli rastgele baytlar
    // base64url: standard base64'ten + → - ve / → _ değişimi, padding tamamla
    let b64 = btoa(String.fromCharCode(...a)).replace(/\+/g, '-').replace(/\//g, '_');
    while (b64.length % 4 !== 0) b64 += '=';
    document.getElementById('sk').value = b64;
    document.getElementById('sk').type = 'text';  // Üretilen anahtarı göster
    showAlert('db-alert', 'Yeni SECRET_KEY oluşturuldu. Kaydetmeyi unutmayın!', 'ok');
}

/**
 * DB bağlantısını canlı olarak test eder.
 * db-dot: durum noktası (loading → ok/err)
 * db-stext: durum metni
 * Sonuç gelene kadar spinner gösterilir.
 */
async function testDb() {
    const dot = document.getElementById('db-dot'), txt = document.getElementById('db-stext'), sp = document.getElementById('db-sp');
    dot.className = 'sdot loading';
    txt.textContent = 'Test ediliyor...';
    sp.style.display = 'block';
    try {
        const d = await (await fetch('/api/db-test', { method: 'POST' })).json();
        dot.className = 'sdot ' + (d.success ? 'ok' : 'err');
        txt.textContent = d.message;
    } catch {
        dot.className = 'sdot err';
        txt.textContent = 'Bağlantı kurulamadı.';
    } finally {
        sp.style.display = 'none';
    }
}

/**
 * DB ayarlarını .env'ye kaydeder, bağlantıyı test eder ve tabloları oluşturur.
 * Başarılıysa init_db() sunucuda çalışır — var olan tablolara dokunulmaz.
 */
async function saveDb() {
    const btn = document.getElementById('db-save-txt'), sp = document.getElementById('db-save-sp');
    btn.textContent = 'Kaydediliyor...';
    sp.style.display = 'block';
    hideAlert('db-alert');
    const p = {
        DB_HOST: document.getElementById('db-host').value,
        DB_PORT: document.getElementById('db-port').value,
        DB_USER: document.getElementById('db-user').value,
        DB_PASSWORD: document.getElementById('db-pass').value,
        DB_NAME: document.getElementById('db-name').value,
        SECRET_KEY: document.getElementById('sk').value
    };
    try {
        const d = await (await fetch('/api/db-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(p)
        })).json();
        showAlert('db-alert', d.message, d.success ? 'ok' : 'err');
        if (d.success) {
            // DB kurulumu tamam, sayfa yenilenebilir
        }
    } catch {
        showAlert('db-alert', 'Kayıt hatası.', 'err');
    } finally {
        btn.textContent = '💾 Kaydet & Tabloları Oluştur';
        sp.style.display = 'none';
    }
}

// ── Sender Mode ──────────────────────────────────────────────────────
/**
 * Gönderici formundaki SMTP/SES/API panel görünürlüğünü ayarlar.
 * Seçili mod butonu 'btn-primary', diğerleri 'btn-outline' sınıfı alır.
 * @param {string} mode - 'smtp' | 'ses' | 'api'
 */
function setSenderMode(mode) {
    const modeInput = document.getElementById('s-mode');
    if (modeInput) modeInput.value = mode;
    
    const smtpFields = document.getElementById('smtp-fields');
    const sesFields = document.getElementById('ses-fields');
    const smtpBtn = document.getElementById('mode-smtp-btn');
    const sesBtn = document.getElementById('mode-ses-btn');
    
    if (smtpFields) smtpFields.style.display = mode === 'smtp' ? 'flex' : 'none';
    if (sesFields) sesFields.style.display = mode === 'ses' ? 'flex' : 'none';
    if (smtpBtn) smtpBtn.className = 'btn btn-sm ' + (mode === 'smtp' ? 'btn-primary' : 'btn-outline');
    if (sesBtn) sesBtn.className = 'btn btn-sm ' + (mode === 'ses' ? 'btn-primary' : 'btn-outline');
}

// ── Gönderici Yönetimi ───────────────────────────────────────────────

/**
 * Göndericileri tablosuna yükler (senders-tbody).
 * NOT: settings sayfalarındaki inline JS bu fonksiyonu override edebilir —
 * bu fonksiyon sadece senders-tbody elementi olan sayfalarda çalışır.
 */
async function loadSenders() {
    // settings.html inline JS bu fonksiyonu override eder, burada fallback
    try {
        const d = await (await fetch('/api/senders')).json();
        const tb = document.getElementById('senders-tbody');
        if (!tb) return; // settings sayfasında kart görünümü kullanılıyor
        
        if (!d.data || !d.data.length) {
            tb.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:20px">Henüz gönderici eklenmedi.</td></tr>';
            return;
        }
        tb.innerHTML = d.data.map(s => {
            const isSes = s.sender_mode === 'ses';
            const modeBadge = isSes ? '<span class="chip chip-ok">☁ SES</span>' : '<span class="chip chip-on">📡 SMTP</span>';
            const serverInfo = isSes ? `${s.aws_region || 'us-east-1'}` : `${esc(s.smtp_server || '')}:${s.smtp_port || ''}`;
            return `<tr>
                <td><strong>${esc(s.name)}</strong></td>
                <td style="font-size:11px">${esc(s.email)}</td>
                <td>${modeBadge}</td>
                <td style="font-family:'Space Mono',monospace;font-size:10px">${serverInfo}</td>
                <td><span class="chip ${s.is_active ? 'chip-on' : 'chip-off'}">${s.is_active ? 'Aktif' : 'Pasif'}</span></td>
                <td><div style="display:flex;gap:6px">
                    <button class="btn btn-outline btn-sm" title="Test et" onclick="testSender(${s.id})">🔌</button>
                    <button class="btn btn-outline btn-sm" title="Düzenle" onclick="editSenderFn(${s.id})">✏</button>
                    <button class="btn btn-danger btn-sm" title="Sil" onclick="delSender(${s.id})">🗑</button>
                </div></td></tr>`;
        }).join('');
    } catch (e) { console.error(e); }
}

// Gönderici verisi cache'i — birden fazla select güncellenirken tekrar fetch yapmamak için
let _sendersCache = {};

/**
 * Sayfadaki tüm gönderici select elementlerini doldurur.
 * Hedefler: #c-sender (tek gönderim), #b-sender (toplu), #lf-sender (log filtre), #r-sender (kurallar)
 * Sadece is_active=1 olan göndericiler listelenir.
 */
async function loadSenderSelects() {
    try {
        const d = await (await fetch('/api/senders')).json();
        _sendersCache = {};
        if (d.data) d.data.forEach(s => _sendersCache[s.id] = s);
        const modeLabel = s => {
            if (s.sender_mode === 'ses') return '☁ AWS SES';
            if (s.sender_mode === 'api') return '🔌 ' + detectApiService(s.api_host).short;
            return '📡 SMTP';
        };
        const opts = d.data ? d.data.filter(s => s.is_active).map(s => `<option value="${s.id}">${modeLabel(s)}  —  ${esc(s.name)}  —  ${esc(s.email)}</option>`).join('') : '';
        
        const cSender = document.getElementById('c-sender');
        if (cSender) cSender.innerHTML = '<option value="">— Seç —</option>' + opts;
        
        const bSender = document.getElementById('b-sender');
        if (bSender) bSender.innerHTML = '<option value="">— Seç —</option>' + opts;
        
        const lfSender = document.getElementById('lf-sender');
        if (lfSender) lfSender.innerHTML = '<option value="">Tüm göndericiler</option>' + opts;
        
        const rSender = document.getElementById('r-sender');
        if (rSender) rSender.innerHTML = '<option value="">— Seç —</option>' + (d.data ? d.data.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('') : '');
    } catch (e) { }
}

/**
 * Göndericinin mevcut verilerini forma yükler (düzenleme modu).
 * editSenderId global değişkenini set eder → saveSender() PUT isteği gönderir.
 * Şifre/anahtar alanları boş bırakılır — boş gönderilirse eski değer korunur.
 */
async function editSenderFn(id) {
    const d = await (await fetch('/api/senders')).json();
    const s = d.data && d.data.find(x => x.id === id);
    if (!s) {
        alert('Gönderici bulunamadı.');
        return;
    }
    editSenderId = id;
    document.getElementById('s-name').value = s.name || '';
    document.getElementById('s-email').value = s.email || '';
    const mode = s.sender_mode || 'smtp';
    setSenderMode(mode);
    
    if (mode === 'smtp') {
        document.getElementById('s-smtp').value = s.smtp_server || '';
        document.getElementById('s-port').value = s.smtp_port || 465;
        document.getElementById('s-user').value = s.username || '';
        document.getElementById('s-pass').value = '';
        document.getElementById('s-ssl').checked = !!s.use_ssl;
    } else {
        document.getElementById('s-aws-key').value = '';
        document.getElementById('s-aws-secret').value = '';
        document.getElementById('s-aws-region').value = s.aws_region || 'us-east-1';
        document.getElementById('s-aws-key').placeholder = 'Kayıtlı (boş = değiştirme)';
        document.getElementById('s-aws-secret').placeholder = 'Kayıtlı (boş = değiştirme)';
    }
    
    document.getElementById('sender-form-title').textContent = 'Gönderici Düzenle: ' + s.name;
    document.getElementById('s-cancel-btn').style.display = 'inline-flex';
    document.getElementById('s-btn-txt').textContent = '💾 Güncelle';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/**
 * Gönderici formunu sıfırlar ve yeni ekleme moduna geçer.
 * Tüm alanları temizler, port'u 465'e döndürür, SSL checkbox'ı işaretler.
 */
function cancelSenderEdit() {
    editSenderId = null;
    ['s-name', 's-email', 's-smtp', 's-user', 's-pass', 's-aws-key', 's-aws-secret'].forEach(i => {
        const el = document.getElementById(i);
        if (el) el.value = '';
    });
    const sPort = document.getElementById('s-port');
    if (sPort) sPort.value = '465';
    
    const sSsl = document.getElementById('s-ssl');
    if (sSsl) sSsl.checked = true;
    
    const sAwsRegion = document.getElementById('s-aws-region');
    if (sAwsRegion) sAwsRegion.value = 'us-east-1';
    
    const sAwsKey = document.getElementById('s-aws-key');
    if (sAwsKey) sAwsKey.placeholder = 'AKIA…';
    
    const sAwsSecret = document.getElementById('s-aws-secret');
    if (sAwsSecret) sAwsSecret.placeholder = '••••••••';
    
    setSenderMode('smtp');
    
    const formTitle = document.getElementById('sender-form-title');
    if (formTitle) formTitle.textContent = 'Yeni Gönderici Ekle';
    
    const cancelBtn = document.getElementById('s-cancel-btn');
    if (cancelBtn) cancelBtn.style.display = 'none';
    
    const btnTxt = document.getElementById('s-btn-txt');
    if (btnTxt) btnTxt.textContent = '💾 Kaydet';
}

/**
 * Gönderici formundan veri toplayıp kaydeder.
 * editSenderId null ise POST (yeni), doluysa PUT (güncelleme).
 * Başarılıysa formu sıfırlar ve listeyi yeniler.
 */
async function saveSender() {
    const sp = document.getElementById('s-sp'), btxt = document.getElementById('s-btn-txt');
    if (!sp || !btxt) return;
    
    sp.style.display = 'block';
    btxt.textContent = 'Kaydediliyor...';
    hideAlert('s-alert');
    
    const mode = document.getElementById('s-mode').value;
    const p = {
        name: document.getElementById('s-name').value,
        email: document.getElementById('s-email').value,
        sender_mode: mode,
        is_active: 1,
        smtp_server: document.getElementById('s-smtp').value,
        smtp_port: parseInt(document.getElementById('s-port').value) || 465,
        username: document.getElementById('s-user').value,
        password: document.getElementById('s-pass').value,
        use_ssl: document.getElementById('s-ssl').checked ? 1 : 0,
        aws_access_key: document.getElementById('s-aws-key').value,
        aws_secret_key: document.getElementById('s-aws-secret').value,
        aws_region: document.getElementById('s-aws-region').value,
    };
    
    const url = editSenderId ? `/api/senders/${editSenderId}` : '/api/senders';
    const method = editSenderId ? 'PUT' : 'POST';
    
    try {
        const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) });
        if (!res.ok) {
            const text = await res.text();
            showAlert('s-alert', `Sunucu hatası (${res.status}): ${text}`, 'err');
            return;
        }
        const d = await res.json();
        showAlert('s-alert', d.message, d.success ? 'ok' : 'err');
        if (d.success) {
            cancelSenderEdit();
            loadSenders();
            loadSenderSelects();
        }
    } catch (e) {
        showAlert('s-alert', 'Bağlantı hatası: ' + e.message, 'err');
        console.error('saveSender hatası:', e);
    } finally {
        sp.style.display = 'none';
        btxt.textContent = '💾 Kaydet';
    }
}

/**
 * Gönderici bağlantısını canlı test eder ve sonucu s-alert'te gösterir.
 * API modunda HTTP isteği, SMTP modunda bağlantı kurma testi yapılır.
 */
async function testSender(id) {
    const d = await (await fetch(`/api/senders/${id}/test`, { method: 'POST' })).json();
    const icon = d.success ? '✅' : '❌';
    showAlert('s-alert', icon + ' ' + d.message, d.success ? 'ok' : 'err');
}

/**
 * Göndericiyi siler (onay dialogu ile).
 * DB'de ON DELETE CASCADE: ilgili kurallar ve loglar da silinir.
 */
async function delSender(id) {
    if (!confirm('Bu göndericiye ait tüm loglar da silinecek. Emin misiniz?')) return;
    const d = await (await fetch(`/api/senders/${id}`, { method: 'DELETE' })).json();
    if (d.success) {
        loadSenders();         // Tabloyu yenile
        loadSenderSelects();   // Tüm select'leri güncelle
    } else alert(d.message);
}

// ── Kural Yönetimi ───────────────────────────────────────────────────

/**
 * Gönderim kurallarını rules-tbody tablosuna yükler.
 * Her satırda: kural adı, gönderici, aralık, durum, düzenle/sil butonları.
 */
async function loadRules() {
    try {
        const d = await (await fetch('/api/rules')).json();
        const tb = document.getElementById('rules-tbody');
        if (!tb) return;
        
        if (!d.data || !d.data.length) {
            tb.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:20px">Henüz kural eklenmedi.</td></tr>';
            return;
        }
        tb.innerHTML = d.data.map(r => {
            const iv = r.min_interval_h == 0 ? 'Sınırsız' : (r.min_interval_h < 24 ? r.min_interval_h + 's' : Math.round(r.min_interval_h / 24) + 'g');
            return `<tr><td><strong>${esc(r.name)}</strong></td><td style="font-size:11px">${esc(r.sender_name || '')} &lt;${esc(r.sender_email || '')}&gt;</td><td><span class="chip chip-skip">⏱ ${iv}</span></td><td><span class="chip ${r.is_active ? 'chip-on' : 'chip-off'}">${r.is_active ? 'Aktif' : 'Pasif'}</span></td><td><div style="display:flex;gap:6px"><button class="btn btn-outline btn-sm" onclick="editRuleFn(${r.id},'${esc(r.name)}',${r.sender_id},${r.min_interval_h})">✏</button><button class="btn btn-danger btn-sm" onclick="delRule(${r.id})">🗑</button></div></td></tr>`;
        }).join('');
        
        const bRule = document.getElementById('b-rule');
        if (bRule) {
            const cur = bRule.value;
            bRule.innerHTML = '<option value="">— Kural yok (sınırsız) —</option>' + (d.data ? d.data.filter(r => r.is_active).map(r => `<option value="${r.id}" data-interval="${r.min_interval_h}">${esc(r.name)}</option>`).join('') : '');
            if (cur) bRule.value = cur;
        }
    } catch (e) { console.error(e); }
}

function editRuleFn(id, name, sid, ih) {
    editRuleId = id;
    document.getElementById('r-name').value = name;
    document.getElementById('r-sender').value = sid;
    document.getElementById('r-interval').value = ih;
    updateIPreview();
    document.getElementById('rule-form-title').textContent = 'Kural Düzenle: ' + name;
    document.getElementById('r-cancel-btn').style.display = 'inline-flex';
    document.getElementById('r-btn-txt').textContent = '💾 Güncelle';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function cancelRuleEdit() {
    editRuleId = null;
    document.getElementById('r-name').value = '';
    document.getElementById('r-sender').value = '';
    document.getElementById('r-interval').value = 0;
    updateIPreview();
    document.getElementById('rule-form-title').textContent = 'Yeni Kural Ekle';
    document.getElementById('r-cancel-btn').style.display = 'none';
    document.getElementById('r-btn-txt').textContent = '💾 Kaydet';
}

async function saveRule() {
    const sp = document.getElementById('r-sp'), btxt = document.getElementById('r-btn-txt');
    sp.style.display = 'block';
    btxt.textContent = 'Kaydediliyor...';
    hideAlert('r-alert');
    
    const p = {
        name: document.getElementById('r-name').value,
        sender_id: parseInt(document.getElementById('r-sender').value) || null,
        min_interval_h: parseInt(document.getElementById('r-interval').value) || 0,
        is_active: 1
    };
    
    if (!p.name || !p.sender_id) {
        showAlert('r-alert', 'Ad ve gönderici zorunludur.', 'err');
        sp.style.display = 'none';
        btxt.textContent = '💾 Kaydet';
        return;
    }
    
    const url = editRuleId ? `/api/rules/${editRuleId}` : '/api/rules';
    const method = editRuleId ? 'PUT' : 'POST';
    
    try {
        const d = await (await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) })).json();
        showAlert('r-alert', d.message, d.success ? 'ok' : 'err');
        if (d.success) {
            cancelRuleEdit();
            loadRules();
        }
    } catch {
        showAlert('r-alert', 'İstek hatası.', 'err');
    } finally {
        sp.style.display = 'none';
        btxt.textContent = '💾 Kaydet';
    }
}

/** Kuralı siler ve listeyi yeniler. */
async function delRule(id) {
    if (!confirm('Kuralı silmek istediğinizden emin misiniz?')) return;
    const d = await (await fetch(`/api/rules/${id}`, { method: 'DELETE' })).json();
    if (d.success) loadRules();
    else alert(d.message);
}

// ── Tek Gönderim ────────────────────────────────────────────────────

/**
 * Tek e-posta gönderir (/api/send — multipart/form-data).
 * Ek dosya varsa attachment olarak eklenir.
 * HTML modu kapalıysa sunucu düz metni HTML'e çevirir.
 */
async function sendSingle() {
    const sp = document.getElementById('c-sp'), btxt = document.getElementById('c-btn-txt');
    sp.style.display = 'block';
    btxt.textContent = 'Gönderiliyor...';
    hideAlert('c-alert');
    
    const fd = new FormData();
    fd.append('sender_id', document.getElementById('c-sender').value);
    fd.append('recipient', document.getElementById('c-to').value);
    fd.append('subject', document.getElementById('c-subject').value);
    fd.append('body', document.getElementById('c-body').value);
    fd.append('html_mode', document.getElementById('c-html').checked ? 'true' : 'false');
    fd.append('include_unsubscribe', document.getElementById('c-unsub') && document.getElementById('c-unsub').checked ? 'true' : 'false');
    
    const f = document.getElementById('c-file');
    if (f.files[0]) fd.append('attachment', f.files[0]);
    
    try {
        const d = await (await fetch('/api/send', { method: 'POST', body: fd })).json();
        showAlert('c-alert', d.message, d.success ? 'ok' : 'err');
    } catch {
        showAlert('c-alert', 'İstek hatası.', 'err');
    } finally {
        sp.style.display = 'none';
        btxt.textContent = 'E-posta Gönder →';
    }
}

// ── Toplu Gönderim ───────────────────────────────────────────────────

/**
 * Toplu gönderim kaynak sekmesini değiştirir: 'db' | 'excel'.
 * Aktif sekme degradeli (mor) arka plan alır, diğeri şeffaf kalır.
 * listSource global değişkeni startBulk() tarafından okunur.
 */
function switchListSource(src) {
    listSource = src;
    // Tüm panel ve sekme referansları
    const panels = {
        db:    document.getElementById('src-db-panel'),
        excel: document.getElementById('src-excel-panel'),
        paste: document.getElementById('src-paste-panel'),
    };
    const tabs = {
        db:    document.getElementById('src-tab-db'),
        excel: document.getElementById('src-tab-excel'),
        paste: document.getElementById('src-tab-paste'),
    };
    // Tüm panelleri gizle, aktif olanı göster
    Object.entries(panels).forEach(([key, el]) => {
        if (el) el.style.display = key === src ? 'flex' : 'none';
    });
    // Sekme stillerini güncelle — aktif sekme renkli, diğerleri outline
    const activeStyle = 'linear-gradient(135deg,var(--accent),#8b5cf6)';
    Object.entries(tabs).forEach(([key, el]) => {
        if (!el) return;
        const active = key === src;
        el.style.background = active ? activeStyle : 'transparent';
        el.style.color       = active ? '#fff' : 'var(--text)';
        el.style.border      = active ? 'none' : '1px solid var(--border2)';
    });
}

/**
 * /api/list-tables endpoint'inden kullanıcı tablolarını çeker ve
 * b-db-table select element'ine doldurur.
 * Her option'ın data-cols attribute'ı sütun listesini JSON olarak taşır.
 */
async function loadDbTables() {
    const sel = document.getElementById('b-db-table');
    if (!sel) return;

    const alertEl = document.getElementById('db-table-alert');

    sel.disabled = true;
    sel.innerHTML = '<option value="">⏳ Tablolar yükleniyor...</option>';
    if (alertEl) alertEl.className = 'alert';

    try {
        const res = await fetch('/api/list-tables');
        if (!res.ok) throw new Error('Sunucu hatası: ' + res.status);
        const d = await res.json();

        if (!d.success) {
            sel.innerHTML = '<option value="">— Tablo seç —</option>';
            if (alertEl) {
                alertEl.textContent = 'Tablo listesi alınamadı: ' + (d.message || 'Bilinmeyen hata');
                alertEl.className = 'alert err show';
            }
            return;
        }

        const tables = d.tables || [];
        const cur = sel.value;
        sel.innerHTML = '<option value="">— Tablo seç —</option>' +
            tables.map(t => `<option value="${esc(t.name)}" data-cols='${JSON.stringify(t.columns)}'>${esc(t.name)} (${t.row_count} kayıt)</option>`).join('');

        if (tables.length === 0 && alertEl) {
            alertEl.textContent = 'Henüz veritabanında kullanici tablosu yok. Excel den ice aktarin.';
            alertEl.className = 'alert show';
        }

        if (cur) sel.value = cur;
    } catch (e) {
        sel.innerHTML = '<option value="">— Tablo seç —</option>';
        if (alertEl) {
            alertEl.textContent = 'Baglanti hatasi: ' + (e.message || 'DB ayarlarini kontrol edin.');
            alertEl.className = 'alert err show';
        }
        console.error('loadDbTables:', e);
    } finally {
        sel.disabled = false;
    }
}

/**
 * Kullanıcı DB tablosu seçtiğinde çalışır.
 * /api/table-preview ile 5 satır önizleme ve sütun listesi alır.
 * E-posta sütununu otomatik tahmin eder (mail/email/eposta içeren sütun adı).
 * Sütunlardan değişken etiketleri ({{sütun}}) oluşturur.
 */
async function onDbTableSelect() {
    const sel   = document.getElementById('b-db-table');
    const tname = sel.value;
    const meta = document.getElementById('b-db-meta');
    const loading = document.getElementById('b-db-loading');
    
    if (!tname) {
        if (meta) meta.style.display = 'none';
        return;
    }
    
    if (loading) loading.style.display = 'block';
    if (meta) meta.style.display = 'none';
    hideAlert('db-table-alert');
    
    try {
        const d = await (await fetch('/api/table-preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ table_name: tname })
        })).json();
        
        if (!d.success) {
            showAlert('db-table-alert', d.message, 'err');
            return;
        }
        
        const esel = document.getElementById('b-db-email-col');
        if (esel) {
            esel.innerHTML = d.columns.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
            const auto = d.columns.find(c => /mail|e.?mail|eposta|email/i.test(c));
            if (auto) esel.value = auto;
        }
        
        const vsel = document.getElementById('b-db-var-cols');
        if (vsel) {
            vsel.innerHTML = d.columns.map(c => `<option value="${esc(c)}" selected>${esc(c)}</option>`).join('');
        }
        
        const totalEl = document.getElementById('b-db-total');
        if (totalEl) totalEl.textContent = d.total;
        
        const prevTbl = document.getElementById('b-db-prev-tbl');
        if (prevTbl) {
            const th = '<tr>' + d.columns.map(c => `<th>${esc(c)}</th>`).join('') + '</tr>';
            const tb = d.preview.map(r => '<tr>' + d.columns.map(c => `<td>${esc(r[c] ?? '')}</td>`).join('') + '</tr>').join('');
            prevTbl.innerHTML = `<table><thead>${th}</thead><tbody>${tb}</tbody></table>`;
        }
        
        updateVarTagsFromDb(d.columns);
        if (meta) meta.style.display = 'block';

        // is_valid kolonu var mı? → filtre toggle'ını göster/gizle
        const filterRow  = document.getElementById('b-valid-filter-row');
        const filterHint = document.getElementById('b-valid-filter-hint');
        const hasValid   = d.columns.includes('is_valid');
        if (filterRow) filterRow.style.display = hasValid ? '' : 'none';
        if (filterRow && !hasValid) {
            // Kolon yok — toggle'ı gizle, checkbox'ı kapat
            const cb = document.getElementById('b-only-valid');
            if (cb) cb.checked = false;
        }
        if (filterHint && hasValid) {
            // Kaç geçerli adres var bilgisini göster
            try {
                const vr = await (await fetch('/api/table-valid-count', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({table_name: tname})
                })).json();
                if (vr.success) {
                    const pct = d.total > 0 ? Math.round(vr.valid / d.total * 100) : 0;
                    filterHint.textContent =
                        `Bu tabloda ${vr.valid} geçerli (%${pct}), ` +
                        `${vr.invalid} geçersiz, ${vr.risky} riskli, ` +
                        `${vr.unchecked} kontrol edilmemiş adres var.`;
                }
            } catch(e) { /* sessizce geç */ }
        }
    } catch (e) {
        showAlert('db-table-alert', 'Tablo okunamadı: ' + e, 'err');
    } finally {
        if (loading) loading.style.display = 'none';
    }
}

function updateVarTagsFromDb(cols) {
    if (!cols) {
        const vsel = document.getElementById('b-db-var-cols');
        if (vsel) cols = Array.from(vsel.options).map(o => o.value);
    }
    const div = document.getElementById('b-db-var-tags');
    if (div && cols) {
        div.innerHTML = cols.map(c => `<span class="var-tag" onclick="insertVar('${c.replace(/'/g, "\\'")}')">${'{{' + esc(c) + '}}'}</span>`).join('');
    }
}

// ── Excel Önizleme ve İçe Aktarım ────────────────────────────────────

/**
 * Excel dosyası seçildiğinde çalışır.
 * /api/preview-excel ile sütunlar ve ilk 5 satır alınır.
 * E-posta sütunu otomatik tahmin edilir.
 * Önizleme tablosu ve değişken etiketleri güncellenir.
 * Sonrasında promptExcelImport() ile DB import modalı gösterilir.
 */
async function previewExcel(input) {
    const file = input.files[0];
    if (!file) return;
    
    const fnEl = document.getElementById('b-excel-fn');
    if (fnEl) fnEl.textContent = '📊 ' + file.name;
    
    const loading = document.getElementById('b-excel-loading');
    if (loading) loading.style.display = 'block';
    
    const meta = document.getElementById('b-excel-meta');
    if (meta) meta.style.display = 'none';
    
    const fd = new FormData();
    fd.append('excel', file);
    
    try {
        const d = await (await fetch('/api/preview-excel', { method: 'POST', body: fd })).json();
        if (!d.success) {
            alert(d.message);
            return;
        }
        
        const esel = document.getElementById('b-email-col');
        if (esel) {
            esel.innerHTML = d.columns.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('');
            const auto = d.columns.find(c => /mail|e.?mail|eposta|email/i.test(c));
            if (auto) esel.value = auto;
        }
        
        const vsel = document.getElementById('b-var-cols');
        if (vsel) {
            vsel.innerHTML = d.columns.map(c => `<option value="${esc(c)}" selected>${esc(c)}</option>`).join('');
        }
        
        const totalEl = document.getElementById('b-total');
        if (totalEl) totalEl.textContent = d.total;
        
        const prevTbl = document.getElementById('b-prev-tbl');
        if (prevTbl) {
            const th = '<tr>' + d.columns.map(c => `<th>${esc(c)}</th>`).join('') + '</tr>';
            const tb = d.preview.map(r => '<tr>' + d.columns.map(c => `<td>${esc(r[c] ?? '')}</td>`).join('') + '</tr>').join('');
            prevTbl.innerHTML = `<table><thead>${th}</thead><tbody>${tb}</tbody></table>`;
        }
        
        updateVarTags(d.columns);
        if (meta) meta.style.display = 'block';
        
        // Excel import modalını göster
        promptExcelImport(file, d.columns);
    } catch (e) {
        alert('Hata: ' + e);
    } finally {
        if (loading) loading.style.display = 'none';
    }
}

function updateVarTags(cols) {
    if (!cols) {
        const vsel = document.getElementById('b-var-cols');
        if (vsel) cols = Array.from(vsel.options).map(o => o.value);
    }
    const div = document.getElementById('b-var-tags');
    if (div && cols) {
        div.innerHTML = cols.map(c => `<span class="var-tag" onclick="insertVar('${c.replace(/'/g, "\\'")}')">${'{{' + esc(c) + '}}'}</span>`).join('');
    }
}

/**
 * {{değişken}} etiketini aktif metin alanına (activeTarget) imlecin olduğu konuma ekler.
 * Seçili metin varsa üzerine yazar; yoksa imlecin hemen sağına ekler.
 * activeTarget: 'b-body' (mesaj) veya 'b-subject' (konu)
 */
function insertVar(col) {
    const el = document.getElementById(activeTarget || 'b-body');
    if (!el) return;
    const tag = '{{' + col + '}}';
    const s   = el.selectionStart, e2 = el.selectionEnd;
    el.value  = el.value.slice(0, s) + tag + el.value.slice(e2);
    el.selectionStart = el.selectionEnd = s + tag.length;
    el.focus();
}

// ── Excel DB Aktarım Modalı ──────────────────────────────────────────

/**
 * Excel import modalını hazırlar ve gösterir.
 * Tablo adını dosya adından türetir (özel karakterler _ ile değiştirilir).
 * Tablo zaten varsa üzerine yaz/ekle/dedupe seçenekleri gösterilir.
 * @param {File} file      - Seçilen Excel dosyası
 * @param {string[]} columns - Excel sütun adları listesi
 */
async function promptExcelImport(file, columns) {
    currentExcelFile = file;
    currentDfColumns = columns;
    
    const defaultTableName = file.name.replace(/\.[^/.]+$/, "").replace(/[^a-zA-Z0-9_]/g, '_').toLowerCase();
    
    // Tablo var mı kontrol et
    const existsCheck = await (await fetch('/api/check-table-exists', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ table_name: defaultTableName })
    })).json();
    
    const existingTable = existsCheck.exists;
    
    // Modal içeriğini oluştur
    showImportStep1(defaultTableName, columns, existingTable);
}

/**
 * Import modal içeriğini oluşturur ve gösterir.
 * Sütun eşleştirme alanları: her Excel sütunu için DB sütun adı girilebilir.
 * existingTable=true ise action seçenekleri (new/overwrite/append/append_dedupe) gösterilir.
 */
function showImportStep1(defaultTableName, columns, existingTable) {
    const content = document.getElementById('import-modal-content');
    if (!content) return;
    
    let html = `
        <div style="margin-bottom:20px">
            <p style="color:var(--muted); margin-bottom:16px;">Excel dosyasını veritabanına aktarmak ister misiniz?</p>
            
            <div class="field" style="margin-bottom:16px">
                <label>Tablo Adı</label>
                <input type="text" id="import-table-name" value="${esc(defaultTableName)}" placeholder="tablo_adi" style="font-family:'Space Mono',monospace">
                <div style="font-size:11px; color:var(--muted); margin-top:4px">Tablolar send_log tablosundan ayrı olarak oluşturulacak</div>
            </div>
            
            <div style="margin-bottom:16px">
                <label>Sütun Eşleştirme</label>
                <div style="max-height:200px; overflow-y:auto; border:1px solid var(--border); border-radius:var(--r); padding:10px">
    `;
    
    columns.forEach(col => {
        html += `
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px">
                <span style="min-width:120px; font-size:12px; color:var(--muted)">${esc(col)} →</span>
                <input type="text" class="import-col-map" data-excel="${esc(col)}" value="${esc(col)}" placeholder="veritabanı sütun adı" style="flex:1; font-family:'Space Mono',monospace; font-size:11px; padding:6px 9px">
            </div>
        `;
    });
    
    html += `
                </div>
                <div style="font-size:11px; color:var(--muted); margin-top:4px">Sütun adlarını düzenleyebilirsiniz (Türkçe karakter, boşluk kullanmayın)</div>
            </div>
    `;
    
    if (existingTable) {
        html += `
            <div class="alert show" style="margin-top:16px; background:rgba(251,191,36,.08); border-color:rgba(251,191,36,.2); color:var(--warn)">
                ⚠️ <strong>${esc(defaultTableName)}</strong> tablosu zaten mevcut. Ne yapmak istersiniz?
            </div>
            
            <div style="display:flex; flex-direction:column; gap:10px; margin-top:16px; padding:12px; background:var(--s2); border-radius:var(--r);">
                <label style="display:flex; align-items:center; gap:8px; cursor:pointer">
                    <input type="radio" name="import-action" value="new" checked onchange="onImportActionChange(this.value)">
                    <span>Yeni tablo oluştur (farklı bir isim ver)</span>
                </label>
                <label style="display:flex; align-items:center; gap:8px; cursor:pointer">
                    <input type="radio" name="import-action" value="overwrite" onchange="onImportActionChange(this.value)">
                    <span>Mevcut tabloyu sil ve yeniden oluştur</span>
                </label>
                <label style="display:flex; align-items:center; gap:8px; cursor:pointer">
                    <input type="radio" name="import-action" value="append" onchange="onImportActionChange(this.value)">
                    <span>Mevcut tabloya ekle (tekrar edebilir)</span>
                </label>
                <label style="display:flex; align-items:center; gap:8px; cursor:pointer">
                    <input type="radio" name="import-action" value="append_dedupe" onchange="onImportActionChange(this.value)">
                    <span>Mevcut tabloya ekle, tekrarlayanları atla</span>
                </label>
            </div>
            
            <div id="import-action-warning" style="display:none; margin-top:12px" class="alert err"></div>
        `;
    }
    
    html += `</div>`;
    
    content.innerHTML = html;
    document.getElementById('excel-import-modal').style.display = 'flex';
    
    if (existingTable) {
        document.querySelectorAll('input[name="import-action"]')[0].checked = true;
        importAction = 'new';
    } else {
        importAction = 'new';
    }
}

/**
 * Import action radio butonları değiştiğinde çalışır.
 * importAction global değişkenini günceller.
 * 'new' seçilirse uyarı gizlenir ve tablo adı inputu normale döner.
 */
function onImportActionChange(value) {
    importAction = value;
    
    const warningDiv = document.getElementById('import-action-warning');
    if (!warningDiv) return;
    
    if (value === 'new') {
        warningDiv.style.display = 'none';
        const tableNameInput = document.getElementById('import-table-name');
        if (tableNameInput) tableNameInput.style.borderColor = 'var(--border)';
    } else {
        warningDiv.style.display = 'none';
    }
}

/**
 * Import modalındaki "Aktar" butonuna basıldığında çalışır.
 * 1. Sütun eşleştirmelerini toplar (özel karakterler _ ile değiştirilir)
 * 2. action='new' ise tablo adı çakışmasını kontrol eder
 * 3. /api/import-excel-to-db'ye FormData gönderir
 * 4. Başarılıysa tablo listesini yeniler (loadDbTables)
 */
async function confirmImport() {
    const tableName = document.getElementById('import-table-name').value.trim();
    
    if (!tableName) {
        alert('Tablo adı gerekli');
        return;
    }
    
    // Sütun eşleştirmelerini al
    const colMappings = {};
    document.querySelectorAll('.import-col-map').forEach(input => {
        const excelCol = input.dataset.excel;
        const dbCol = input.value.trim().replace(/[^a-zA-Z0-9_]/g, '_');
        if (dbCol) {
            colMappings[excelCol] = dbCol;
        }
    });
    
    if (Object.keys(colMappings).length === 0) {
        alert('En az bir sütun eşlemesi yapmalısınız');
        return;
    }
    
    // Yeni tablo isteniyorsa ama aynı isim varsa uyar
    if (importAction === 'new') {
        const existsCheck = await (await fetch('/api/check-table-exists', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ table_name: tableName })
        })).json();
        
        if (existsCheck.exists) {
            document.getElementById('import-action-warning').style.display = 'block';
            document.getElementById('import-action-warning').textContent = `"${tableName}" tablosu zaten var. Lütfen farklı bir isim seçin veya diğer seçenekleri kullanın.`;
            document.getElementById('import-table-name').style.borderColor = 'var(--err)';
            return;
        }
    }
    
    // Aktarımı başlat
    const fd = new FormData();
    fd.append('excel', currentExcelFile);
    fd.append('table_name', tableName);
    fd.append('column_names', JSON.stringify(colMappings));
    fd.append('action', importAction);
    
    const btn = document.getElementById('import-confirm-btn');
    const originalText = btn.textContent;
    btn.textContent = 'Aktarılıyor...';
    btn.disabled = true;
    
    try {
        const d = await (await fetch('/api/import-excel-to-db', {
            method: 'POST',
            body: fd
        })).json();
        
        if (d.success) {
            alert(`✅ ${d.message}`);
            closeImportModal();
            loadDbTables(); // Tablo listesini yenile
        } else {
            alert(`❌ ${d.message}`);
        }
    } catch (e) {
        alert('Hata: ' + e);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

/** Import modalını kapatır ve global durumu sıfırlar. */
function closeImportModal() {
    document.getElementById('excel-import-modal').style.display = 'none';
    currentExcelFile = null;
    currentDfColumns = [];
    importAction     = 'new';
}

/**
 * Toplu gönderimi başlatır — kaynak seçimine göre yönlendirir.
 * listSource='db'    → startBulkFromDb()
 * listSource='excel' → Excel dosyasını okuyup /api/send-bulk'a gönderir
 *
 * PARTI SİSTEMİ:
 *   batchEnabled=true ise gönderim batchSize'lık parçalara bölünür.
 *   Her parti arası batchWait dakika beklenir (showBatchCountdown).
 *   Bu sayede AWS SES günlük kota aşımı önlenir.
 *
 * SSE OKUMA:
 *   fetch() response.body.getReader() ile satır satır okunur.
 *   Her 'data: {...}' satırı handleBulkEvent() ile işlenir.
 *   AbortController: "Durdur" butonuna basılınca stream iptal edilir.
 */
async function startBulk() {
    if (listSource === 'db') return startBulkFromDb();
    if (listSource === 'paste') return startBulkFromPaste();

    // EXCEL KAYNAĞI
    const excel = document.getElementById('b-excel').files[0];
    if (!excel) { showAlert('b-alert', 'Önce Excel dosyası yükleyin.', 'err'); return; }

    const sid  = document.getElementById('b-sender').value;
    const ecol = document.getElementById('b-email-col').value;
    const subj = document.getElementById('b-subject').value.trim();
    const body = document.getElementById('b-body').value.trim();
    if (!sid || !ecol || !subj || !body) {
        showAlert('b-alert', 'Gönderici, e-posta sütunu, konu ve mesaj zorunludur.', 'err'); return;
    }

    const batchEnabled = document.getElementById('b-batch-enabled') && document.getElementById('b-batch-enabled').checked;
    const batchSize    = batchEnabled ? parseInt(document.getElementById('b-batch-size').value) : 0;
    // b-batch-wait hidden input'a calcBatchWaitMinutes() toplam dakikayı yazar
    const batchWait    = batchEnabled ? (parseInt(document.getElementById('b-batch-wait')?.value) || 60) : 0;

    const btn = document.getElementById('b-send-btn');
    const sp  = document.getElementById('b-sp');
    const btxt = document.getElementById('b-btn-txt');
    const stopBtn = document.getElementById('b-stop-btn');
    btn.disabled = true; sp.style.display = 'block'; btxt.textContent = 'Gönderiliyor...';
    if (stopBtn) stopBtn.style.display = 'inline-flex';
    hideAlert('b-alert');
    document.getElementById('b-prog-wrap').style.display = 'block';
    document.getElementById('b-log').innerHTML = '';
    ['b-ok','b-err','b-skip','b-tot'].forEach(id => { const el=document.getElementById(id); if(el) el.textContent='0'; });
    const fill = document.getElementById('b-fill'); if (fill) fill.style.width = '0%';

    window._bulkAbort = new AbortController();
    window._bulkStopped = false;

    const vsel = document.getElementById('b-var-cols');
    const varCols = Array.from(vsel.selectedOptions).map(o => o.value).join(',');
    const att = document.getElementById('b-att');

    // Toplam satır sayısını öğren
    let totalRows = 0;
    try {
        const countFd = new FormData();
        countFd.append('excel', excel);
        countFd.append('email_col', ecol);
        const cr = await (await fetch('/api/count-excel-rows', { method: 'POST', body: countFd })).json();
        totalRows = cr.count || 0;
    } catch(e) { totalRows = 0; }

    const partCount = batchEnabled && batchSize > 0 ? Math.ceil(totalRows / batchSize) : 1;
    const titleEl = document.getElementById('b-prog-title');
    if (titleEl) titleEl.textContent = partCount > 1 ? `Gönderim Durumu (${partCount} parti)` : 'Gönderim Durumu';

    for (let part = 0; part < (batchEnabled && batchSize > 0 ? partCount : 1); part++) {
        if (window._bulkStopped) break;
        const offset = batchEnabled && batchSize > 0 ? part * batchSize : 0;
        if (partCount > 1 && titleEl) titleEl.textContent = `Gönderim Durumu — Parti ${part+1} / ${partCount}`;

        const fd = new FormData();
        fd.append('excel', excel);
        fd.append('sender_id', sid);
        fd.append('rule_id', document.getElementById('b-rule').value || '');
        fd.append('email_col', ecol);
        fd.append('var_cols', varCols);
        fd.append('subject', subj);
        fd.append('body', body);
        fd.append('html_mode', document.getElementById('b-html').checked ? 'true' : 'false');
        fd.append('include_unsubscribe', document.getElementById('b-unsub') && document.getElementById('b-unsub').checked ? 'true' : 'false');
        fd.append('delay_ms', document.getElementById('b-delay').value);
        if (att.files[0]) fd.append('attachment', att.files[0]);
        if (batchEnabled && batchSize > 0) { fd.append('batch_offset', offset); fd.append('batch_limit', batchSize); }

        const partOk = await _bulkFetchWithRetry('/api/send-bulk', fd);
        if (!partOk) break;
        if (window._bulkStopped) break;

        // Son parti değilse geri say
        if (batchEnabled && part < partCount - 1) {
            await showBatchCountdown(batchWait, part + 1, partCount);
        }
    }

    if (window._bulkStopped) {
        const log = document.getElementById('b-log');
        if (log) log.innerHTML += '<div class="l-err">⏹ Gönderim kullanıcı tarafından durduruldu.</div>';
    }
    btn.disabled = false; sp.style.display = 'none'; btxt.textContent = '🚀 Toplu Gönderimi Başlat';
    if (stopBtn) stopBtn.style.display = 'none';
    window._bulkStopped = false;
}

/**
 * DB tablosundan toplu gönderim yapar (/api/send-bulk-ses SSE stream).
 * startBulk() ile aynı parti/SSE mantığı, farklı endpoint ve form alanları.
 * DB kaynağında var_cols: b-db-var-cols select'inden alınır.
 */
async function startBulkFromDb() {
    const tname = document.getElementById('b-db-table').value;
    const ecol  = document.getElementById('b-db-email-col').value;
    const sid   = document.getElementById('b-sender').value;
    const subj  = document.getElementById('b-subject').value.trim();
    const body  = document.getElementById('b-body').value.trim();
    if (!tname || !ecol || !sid || !subj || !body) {
        showAlert('b-alert', 'Tablo, e-posta sütunu, gönderici, konu ve mesaj zorunludur.', 'err'); return;
    }

    const batchEnabled = document.getElementById('b-batch-enabled') && document.getElementById('b-batch-enabled').checked;
    const batchSize    = batchEnabled ? parseInt(document.getElementById('b-batch-size').value) : 0;
    // b-batch-wait hidden input'a calcBatchWaitMinutes() toplam dakikayı yazar
    const batchWait    = batchEnabled ? (parseInt(document.getElementById('b-batch-wait')?.value) || 60) : 0;

    const btn = document.getElementById('b-send-btn');
    const sp  = document.getElementById('b-sp');
    const btxt = document.getElementById('b-btn-txt');
    const stopBtn = document.getElementById('b-stop-btn');
    btn.disabled = true; sp.style.display = 'block'; btxt.textContent = 'Gönderiliyor...';
    if (stopBtn) stopBtn.style.display = 'inline-flex';
    hideAlert('b-alert');
    document.getElementById('b-prog-wrap').style.display = 'block';
    document.getElementById('b-log').innerHTML = '';
    ['b-ok','b-err','b-skip','b-tot'].forEach(id => { const el=document.getElementById(id); if(el) el.textContent='0'; });
    const fill = document.getElementById('b-fill'); if (fill) fill.style.width = '0%';

    window._bulkAbort = new AbortController();
    window._bulkStopped = false;

    // Toplam satır sayısını öğren
    let totalRows = 0;
    try {
        const cr = await (await fetch(`/api/count-table-rows?table_name=${encodeURIComponent(tname)}&email_col=${encodeURIComponent(ecol)}`)).json();
        totalRows = cr.count || 0;
    } catch(e) { totalRows = 0; }

    const partCount = batchEnabled && batchSize > 0 ? Math.ceil(totalRows / batchSize) : 1;
    const titleEl = document.getElementById('b-prog-title');
    if (titleEl) titleEl.textContent = partCount > 1 ? `Gönderim Durumu (${partCount} parti)` : 'Gönderim Durumu';

    const att = document.getElementById('b-att');

    for (let part = 0; part < (batchEnabled && batchSize > 0 ? partCount : 1); part++) {
        if (window._bulkStopped) break;
        const offset = batchEnabled && batchSize > 0 ? part * batchSize : 0;
        if (partCount > 1 && titleEl) titleEl.textContent = `Gönderim Durumu — Parti ${part+1} / ${partCount}`;

        const fd = new FormData();
        fd.append('sender_id', sid);
        fd.append('rule_id', document.getElementById('b-rule').value || '');
        fd.append('table_name', tname);
        fd.append('email_col', ecol);
        fd.append('subject', subj);
        fd.append('body', body);
        fd.append('html_mode', document.getElementById('b-html').checked ? 'true' : 'false');
        fd.append('include_unsubscribe', document.getElementById('b-unsub') && document.getElementById('b-unsub').checked ? 'true' : 'false');
        fd.append('delay_ms', document.getElementById('b-delay').value);
        if (att.files[0]) fd.append('attachment', att.files[0]);
        if (batchEnabled && batchSize > 0) { fd.append('batch_offset', offset); fd.append('batch_limit', batchSize); }

        const partOk = await _bulkFetchWithRetry('/api/send-bulk-ses', fd);
        if (!partOk) break;
        if (window._bulkStopped) break;

        if (batchEnabled && part < partCount - 1) {
            await showBatchCountdown(batchWait, part + 1, partCount);
        }
    }

    if (window._bulkStopped) {
        const log = document.getElementById('b-log');
        if (log) log.innerHTML += '<div class="l-err">⏹ Gönderim kullanıcı tarafından durduruldu.</div>';
    }
    btn.disabled = false; sp.style.display = 'none'; btxt.textContent = '🚀 Toplu Gönderimi Başlat';
    if (stopBtn) stopBtn.style.display = 'none';
    window._bulkStopped = false;
}

/**
/**
 * SSE stream'den gelen tek bir olayı işler ve b-log'a satır ekler.
 * Olay tipleri:
 *   'start'    → toplam sayıyı göster, log mesajı ekle
 *   'progress' → ilerleme çubuğunu güncelle, ok/skip/err sayaçlarını artır
 *   'done'     → %100 ilerleme, özet satırı, EC2 auto-stop kontrolü
 *   'error'    → hata mesajı göster
 * log.scrollTop = scrollHeight: her satırda otomatik aşağı kaydır.
 */

/* Gönderim sonuçlarını tutan bellek — export için */
window._bulkLogData = [];
/* Gönderim başlangıç zamanı */
window._bulkStartTime = null;

function handleBulkEvent(ev) {
    const log = document.getElementById('b-log');
    if (!log) return;
    
    const add = (cls, html) => {
        log.innerHTML += `<div class="${cls}">${html}</div>`;
        log.scrollTop = log.scrollHeight;
    };
    
    if (ev.type === 'start') {
        const tot = document.getElementById('b-tot');
        if (tot) tot.textContent = ev.total;
        window._bulkLogData = [];
        window._bulkStartTime = new Date();
        // Export butonlarını gizle (yeni gönderim başladı)
        const expBtns = document.getElementById('b-export-btns');
        if (expBtns) expBtns.style.display = 'none';
        add('l-info', `📋 ${ev.total} alıcıya gönderim başlıyor...`);
    } else if (ev.type === 'progress') {
        const pct = Math.round(ev.i / ev.total * 100);
        const fill = document.getElementById('b-fill');
        if (fill) fill.style.width = pct + '%';
        
        if (ev.status === 'ok') {
            const ok = document.getElementById('b-ok');
            if (ok) ok.textContent = parseInt(ok.textContent) + 1;
            add('l-ok', `✓ [${ev.i}/${ev.total}] ${esc(ev.email)}`);
            window._bulkLogData.push({ sira: ev.i, email: ev.email, durum: 'Başarılı', detay: '' });
        } else if (ev.status === 'skipped') {
            const skip = document.getElementById('b-skip');
            if (skip) skip.textContent = parseInt(skip.textContent) + 1;
            add('l-skip', `⏭ [${ev.i}/${ev.total}] ${esc(ev.email)} — ${esc(ev.reason || 'atlandı')}`);
            window._bulkLogData.push({ sira: ev.i, email: ev.email, durum: 'Atlandı', detay: ev.reason || '' });
        } else {
            const err = document.getElementById('b-err');
            if (err) err.textContent = parseInt(err.textContent) + 1;
            add('l-err', `✗ [${ev.i}/${ev.total}] ${esc(ev.email)} — ${esc(ev.error || '')}`);
            window._bulkLogData.push({ sira: ev.i, email: ev.email, durum: 'Hatalı', detay: ev.error || '' });
        }
    } else if (ev.type === 'done') {
        const fill = document.getElementById('b-fill');
        if (fill) fill.style.width = '100%';
        
        add('l-info', '──────────────────────');
        add(ev.err > 0 ? 'l-err' : 'l-ok', `🏁 ✓${ev.ok} başarılı  ✗${ev.err} hatalı  ⏭${ev.skipped} atlandı`);
        showAlert('b-alert', `Tamamlandı! ✓${ev.ok} başarılı, ✗${ev.err} hatalı, ⏭${ev.skipped} atlandı`, ev.err === 0 ? 'ok' : 'err');
        loadLog(1);

        // Export butonlarını göster
        const expBtns = document.getElementById('b-export-btns');
        if (expBtns && window._bulkLogData.length > 0) expBtns.style.display = 'flex';

        // EC2 auto-stop
        const autoStop = document.getElementById('ec2-autostop');
        if (autoStop && autoStop.checked) {
            add('l-info', '🖥 EC2 kapatılıyor... 5 saniye içinde bağlantı kesilecek.');
            fetch('/api/ec2-stop', { method: 'POST' }).catch(() => {});
        }
    } else if (ev.type === 'error') {
        add('l-err', '❌ ' + esc(ev.message));
        showAlert('b-alert', ev.message, 'err');
    }
}

/**
 * EC2 durdurma butonuna basıldığında çalışır.
 * Onay dialogu gösterir — kabul edilirse /api/ec2-stop çağrılır.
 * Başarılıysa buton devre dışı bırakılır (geri alınamaz işlem).
 * Sunucu 5 saniye sonra instance'ı durdurduğu için bağlantı kesilecektir.
 */
async function manualStopEc2() {
    const btn = document.getElementById('ec2-stop-btn');
    if (!confirm('EC2 instance\'ı şimdi kapatmak istediğinize emin misiniz?\nBağlantı kesilecek ve uygulamaya erişemeyeceksiniz.')) return;
    btn.disabled = true;
    btn.textContent = '⏳ Kapatılıyor...';
    try {
        const d = await (await fetch('/api/ec2-stop', { method: 'POST' })).json();
        if (d.success) {
            btn.textContent = '✓ Kapatıldı';
            showAlert('b-alert', '🖥 EC2 kapatılıyor. 5 saniye içinde bağlantı kesilecek.', 'ok');
        } else {
            btn.disabled = false;
            btn.textContent = '⏹ Şimdi Kapat';
            showAlert('b-alert', 'EC2 kapatılamadı: ' + d.message, 'err');
        }
    } catch (e) {
        btn.disabled = false;
        btn.textContent = '⏹ Şimdi Kapat';
        showAlert('b-alert', 'Bağlantı hatası: ' + e, 'err');
    }
}

window.manualStopEc2 = manualStopEc2;

/**
 * Gönderim loglarını sayfalı olarak yükler ve log-tbody'e render eder.
 * Filtreler: gönderici (lf-sender), durum (lf-status), arama (lf-search).
 * Her satırda mod rozeti (SES/SMTP/API adı) gösterilir.
 * Sayfalama: pg-prev/pg-next disabled durumu güncellenir.
 * @param {number} page - Yüklenecek sayfa (1'den başlar)
 */
async function loadLog(page) {
    logPage = page;
    
    const lfSender = document.getElementById('lf-sender');
    const lfStatus = document.getElementById('lf-status');
    const lfSearch = document.getElementById('lf-search');
    
    const sid = lfSender ? lfSender.value : '';
    const st = lfStatus ? lfStatus.value : '';
    const sr = lfSearch ? lfSearch.value : '';
    
    let url = `/api/send-log?page=${page}&per_page=50`;
    if (sid) url += `&sender_id=${sid}`;
    if (st) url += `&status=${st}`;
    if (sr) url += `&search=${encodeURIComponent(sr)}`;
    
    try {
        const d = await (await fetch(url)).json();
        const tb = document.getElementById('log-tbody');
        if (!tb) return;
        
        if (!d.data || !d.data.length) {
            tb.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:20px">Kayıt bulunamadı.</td></tr>';
            return;
        }
        
        tb.innerHTML = d.data.map(r => {
            const cls = r.status === 'sent' ? 'chip-ok' : r.status === 'failed' ? 'chip-err' : 'chip-skip';
            const lbl = r.status === 'sent' ? '✓ Gönderildi' : r.status === 'failed' ? '✗ Hata' : '⏭ Atlandı';
            let modeBadge = '';
            if (r.sender_mode === 'api') {
                const svc = detectApiService(r.api_host);
                modeBadge = `<span class="chip chip-skip" style="font-size:9px;padding:1px 5px;margin-left:4px">${svc.short}</span>`;
            } else if (r.sender_mode === 'ses') {
                modeBadge = `<span class="chip chip-ok" style="font-size:9px;padding:1px 5px;margin-left:4px">SES</span>`;
            }
            return `<tr>
                <td style="font-size:11px;white-space:nowrap">${esc(r.sent_at)}</td>
                <td style="font-size:11px">${esc(r.sender_name || '')}${modeBadge}</td>
                <td style="font-size:11px">${esc(r.recipient)}</td>
                <td style="font-size:11px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(r.subject)}">${esc(r.subject)}</td>
                <td><span class="chip ${cls}">${lbl}</span></td>
                <td style="font-size:11px;color:var(--muted)">${r.sent_by_username ? '👤 ' + esc(r.sent_by_username) : '—'}</td>
                <td style="font-size:10px;color:var(--err);max-width:130px;overflow:hidden;text-overflow:ellipsis" title="${esc(r.error_msg || '')}">${esc(r.error_msg || '')}</td>
            </tr>`;
        }).join('');
        
        const pages = Math.ceil(d.total / 50);
        const logCount = document.getElementById('log-count');
        if (logCount) logCount.textContent = `Toplam ${d.total} kayıt`;
        
        const pgInfo = document.getElementById('pg-info');
        if (pgInfo) pgInfo.textContent = `${page} / ${pages || 1}`;
        
        const pgPrev = document.getElementById('pg-prev');
        if (pgPrev) pgPrev.disabled = (page <= 1);
        
        const pgNext = document.getElementById('pg-next');
        if (pgNext) pgNext.disabled = (page >= pages);
    } catch (e) { console.error(e); }
}

// ── Global Fonksiyon Atamalar ────────────────────────────────────────
// HTML şablonlarındaki inline onclick="fnAdi()" çağrıları için gerekli.
// JavaScript modülü olmadığından fonksiyonların window nesnesine atanması şart.
window.togglePw = togglePw;
window.showFn = showFn;
window.setSPort = setSPort;
window.setRInterval = setRInterval;
window.updateIPreview = updateIPreview;
window.onRuleChange = onRuleChange;
window.genKey = genKey;
window.testDb = testDb;
window.saveDb = saveDb;
window.setSenderMode = setSenderMode;
window.loadSenders = loadSenders;
window.loadSenderSelects = loadSenderSelects;
window.editSenderFn = editSenderFn;
window.cancelSenderEdit = cancelSenderEdit;
window.saveSender = saveSender;
window.testSender = testSender;
window.delSender = delSender;
window.loadRules = loadRules;
window.editRuleFn = editRuleFn;
window.cancelRuleEdit = cancelRuleEdit;
window.saveRule = saveRule;
window.delRule = delRule;
window.sendSingle = sendSingle;
window.previewExcel = previewExcel;
window.updateVarTags = updateVarTags;
window.updateVarTagsFromDb = updateVarTagsFromDb;
window.insertVar = insertVar;
window.switchListSource = switchListSource;
window.loadDbTables = loadDbTables;
window.onDbTableSelect = onDbTableSelect;
window.startBulk = startBulk;
window.onImportActionChange = onImportActionChange;
window.confirmImport = confirmImport;
window.closeImportModal = closeImportModal;
window.loadLog = loadLog;
/* ══════════════════════════════════════════════════════════════
   BULK SEND — 502/503/504 OTOMATİK RETRY
   Tek bir parti isteğini gönderir. Gateway/sunucu hatalarında
   MAX_RETRIES kadar tekrar dener, aralarında bekleme sayacı gösterir.
   Dönen değer: true → parti tamamlandı, false → iptal/vazgeçildi
   ══════════════════════════════════════════════════════════════ */

const _RETRY_CODES    = new Set([502, 503, 504]);
const _MAX_RETRIES    = 2;   // ilk deneme + 2 retry = toplam 3 şans
const _RETRY_WAIT_SEC = 10;  // her retry öncesi bekleme (saniye)

/**
 * SSE isteğini gönderir; 502/503/504 alırsa veya ağ hatası olursa
 * otomatik olarak _MAX_RETRIES kez daha dener.
 * Her retry arasında _RETRY_WAIT_SEC saniyelik geri sayım gösterir.
 *
 * @param {string}   endpoint  '/api/send-bulk' veya '/api/send-bulk-ses'
 * @param {FormData} fd        Gönderilecek form verisi
 * @returns {Promise<boolean>} true=başarı/tamamlandı, false=iptal/vazgeçildi
 */
async function _bulkFetchWithRetry(endpoint, fd) {
    const log = document.getElementById('b-log');
    const addLog = (cls, html) => {
        if (!log) return;
        log.innerHTML += `<div class="${cls}">${html}</div>`;
        log.scrollTop = log.scrollHeight;
    };

    // Bu parti için başlangıç offset'i (FormData'dan oku, varsa)
    const baseOffset = parseInt(fd.get('batch_offset') || '0');
    // Kaç mail başarıyla işlendi — kopuş sonrası offset'i ilerletmek için
    let processedInStream = 0;
    // Parti tamamlandı mı (type:'done' eventi alındı mı)
    let streamCompleted = false;

    for (let attempt = 0; attempt <= _MAX_RETRIES; attempt++) {
        if (window._bulkStopped) return false;

        // Retry öncesi: offset'i güncelle (zaten işlenenleri atla)
        if (attempt > 0) {
            const newOffset = baseOffset + processedInStream;
            fd.set('batch_offset', String(newOffset));
            // batch_limit varsa azalt
            const origLimit = parseInt(fd.get('batch_limit') || '0');
            if (origLimit > 0) {
                fd.set('batch_limit', String(Math.max(0, origLimit - processedInStream)));
            }

            // Kullanıcıya bildir
            const reason = streamCompleted ? '' : ' (bağlantı koptu)';
            showAlert('b-alert',
                `⚠️ Sunucu hatası${reason}. ${_RETRY_WAIT_SEC} sn sonra tekrar denenecek... (${attempt}/${_MAX_RETRIES})`,
                'err');
            addLog('l-err',
                `⚠️ Bağlantı kesildi${reason} — ${processedInStream} mail işlendi, kalan ${_RETRY_WAIT_SEC} sn sonra devam edecek (${attempt}/${_MAX_RETRIES})`);

            // Geri sayım
            for (let s = _RETRY_WAIT_SEC; s > 0; s--) {
                if (window._bulkStopped) return false;
                showAlert('b-alert',
                    `⚠️ Sunucu hatası${reason}. Tekrar deneniyor... (${attempt}/${_MAX_RETRIES}) — ${s} sn`,
                    'err');
                await new Promise(r => setTimeout(r, 1000));
            }
            if (window._bulkStopped) return false;
            addLog('l-info', `🔄 Kaldığı yerden devam ediliyor... (deneme ${attempt + 1}, offset: ${baseOffset + processedInStream})`);
            hideAlert('b-alert');

            // Sıfırla — bu retry için sayaçları temizle
            streamCompleted = false;
        }

        try {
            window._bulkAbort = new AbortController();
            const res = await fetch(endpoint, {
                method: 'POST',
                body: fd,
                signal: window._bulkAbort.signal
            });

            // 502/503/504 → retry yap
            if (_RETRY_CODES.has(res.status)) {
                const errText = `HTTP ${res.status}: sunucu geçici olarak yanıt vermiyor.`;
                if (attempt < _MAX_RETRIES) {
                    addLog('l-err', `✗ ${errText}`);
                    continue;
                }
                showAlert('b-alert', `❌ ${errText} Maksimum deneme sayısına ulaşıldı.`, 'err');
                addLog('l-err', `❌ ${errText} Gönderim durdu.`);
                return false;
            }

            // SSE stream'i oku
            const reader = res.body.getReader();
            const dec = new TextDecoder();
            let buf = '';
            while (true) {
                if (window._bulkStopped) { reader.cancel(); return false; }
                let done, value;
                try {
                    ({ done, value } = await reader.read());
                } catch (readErr) {
                    // reader.read() atarsa → bağlantı koptu
                    throw readErr;
                }
                if (done) break;
                buf += dec.decode(value, { stream: true });
                const lines = buf.split('\n\n'); buf = lines.pop();
                for (const line of lines) {
                    if (!line.startsWith('data:')) continue;
                    let ev;
                    try { ev = JSON.parse(line.slice(5).trim()); } catch { continue; }
                    // progress olaylarını say — kopuş sonrası offset için
                    if (ev.type === 'progress') processedInStream++;
                    if (ev.type === 'done') streamCompleted = true;
                    handleBulkEvent(ev);
                }
            }

            // done=true geldi ama 'done' eventi işlenmediyse → bağlantı erken kapandı
            if (!streamCompleted) {
                if (attempt < _MAX_RETRIES) {
                    addLog('l-err', '✗ Bağlantı erken kapandı (remote end closed connection).');
                    continue;  // retry
                }
                showAlert('b-alert', '❌ Sunucu bağlantıyı sürekli kesiyor. Gönderim durdu.', 'err');
                addLog('l-err', '❌ Maksimum deneme sayısına ulaşıldı. Gönderim durdu.');
                return false;
            }

            return true;  // başarılı tamamlandı

        } catch (e) {
            if (window._bulkStopped) return false;
            const errMsg = e && e.message ? e.message : String(e);
            addLog('l-err', `✗ Bağlantı hatası: ${esc(errMsg)}`);
            if (attempt >= _MAX_RETRIES) {
                showAlert('b-alert', `❌ Bağlantı hatası: ${errMsg} — maksimum deneme sayısına ulaşıldı.`, 'err');
                return false;
            }
            // continue → retry
        }
    }
    return false;
}

/* ══════════════════════════════════════════════════════════════
   BULK SEND — EXPORT FONKSİYONLARI
   Gönderim sonuçlarını CSV veya Excel olarak indirir.
   Veri kaynağı: window._bulkLogData (handleBulkEvent tarafından doldurulur)
   ══════════════════════════════════════════════════════════════ */

/**
 * Gönderim log verilerini CSV veya Excel formatında indirir.
 * @param {'csv'|'excel'} format
 */
function exportBulkLog(format) {
    const data = window._bulkLogData || [];
    if (!data.length) { alert('Dışa aktarılacak veri yok.'); return; }

    const startTime = window._bulkStartTime
        ? window._bulkStartTime.toLocaleDateString('tr-TR').replace(/\./g, '-') + '_' +
          window._bulkStartTime.toLocaleTimeString('tr-TR', {hour:'2-digit', minute:'2-digit'}).replace(':', '-')
        : 'rapor';

    const filename = `gondekim_raporu_${startTime}`;

    if (format === 'csv') {
        _exportCSV(data, filename);
    } else {
        _exportExcel(data, filename);
    }
}

/** CSV oluştur ve indir */
function _exportCSV(data, filename) {
    const headers = ['Sıra', 'E-posta', 'Durum', 'Detay'];
    const rows = data.map(r => [
        r.sira,
        r.email,
        r.durum,
        (r.detay || '').replace(/"/g, '""')  // CSV escape
    ]);

    const csvContent = [headers, ...rows]
        .map(row => row.map(cell => `"${cell}"`).join(','))
        .join('\r\n');

    // BOM ekle — Excel Türkçe karakterleri doğru okusun
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    _downloadBlob(blob, filename + '.csv');
}

/** Excel (XLSX) oluştur ve indir — saf JS, kütüphane gerektirmez */
function _exportExcel(data, filename) {
    /* XLSX, binary format gerektirir — basit XML tabanlı SpreadsheetML kullanıyoruz */
    const esc_xml = s => String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');

    const ok_count   = data.filter(r => r.durum === 'Başarılı').length;
    const err_count  = data.filter(r => r.durum === 'Hatalı').length;
    const skip_count = data.filter(r => r.durum === 'Atlandı').length;
    const startStr   = window._bulkStartTime
        ? window._bulkStartTime.toLocaleString('tr-TR')
        : '—';

    /* Stil renkleri satır bazında durum göre */
    const rowColor = durum => {
        if (durum === 'Başarılı') return ' ss:StyleID="ok"';
        if (durum === 'Hatalı')   return ' ss:StyleID="err"';
        if (durum === 'Atlandı')  return ' ss:StyleID="skip"';
        return '';
    };

    const dataRows = data.map(r => `
      <Row>
        <Cell><Data ss:Type="Number">${r.sira}</Data></Cell>
        <Cell${rowColor(r.durum)}><Data ss:Type="String">${esc_xml(r.email)}</Data></Cell>
        <Cell${rowColor(r.durum)}><Data ss:Type="String">${esc_xml(r.durum)}</Data></Cell>
        <Cell><Data ss:Type="String">${esc_xml(r.detay || '')}</Data></Cell>
      </Row>`).join('');

    const xml = `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
          xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
          xmlns:x="urn:schemas-microsoft-com:office:excel">
  <Styles>
    <Style ss:ID="header">
      <Font ss:Bold="1" ss:Color="#FFFFFF"/>
      <Interior ss:Color="#2563EB" ss:Pattern="Solid"/>
      <Alignment ss:Horizontal="Center"/>
    </Style>
    <Style ss:ID="summary_label">
      <Font ss:Bold="1"/>
      <Interior ss:Color="#F1F5F9" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="ok">
      <Interior ss:Color="#DCFCE7" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="err">
      <Interior ss:Color="#FEE2E2" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="skip">
      <Interior ss:Color="#FEF9C3" ss:Pattern="Solid"/>
    </Style>
  </Styles>

  <Worksheet ss:Name="Gönderim Raporu">
    <Table>
      <Column ss:Width="40"/>
      <Column ss:Width="220"/>
      <Column ss:Width="90"/>
      <Column ss:Width="300"/>

      <!-- Özet başlık -->
      <Row>
        <Cell ss:MergeAcross="3" ss:StyleID="header">
          <Data ss:Type="String">📧 Toplu Gönderim Raporu — ${esc_xml(startStr)}</Data>
        </Cell>
      </Row>
      <Row>
        <Cell ss:StyleID="summary_label"><Data ss:Type="String">Toplam</Data></Cell>
        <Cell><Data ss:Type="Number">${data.length}</Data></Cell>
        <Cell ss:StyleID="summary_label"><Data ss:Type="String">Başarılı</Data></Cell>
        <Cell ss:StyleID="ok"><Data ss:Type="Number">${ok_count}</Data></Cell>
      </Row>
      <Row>
        <Cell ss:StyleID="summary_label"><Data ss:Type="String">Hatalı</Data></Cell>
        <Cell ss:StyleID="err"><Data ss:Type="Number">${err_count}</Data></Cell>
        <Cell ss:StyleID="summary_label"><Data ss:Type="String">Atlandı</Data></Cell>
        <Cell ss:StyleID="skip"><Data ss:Type="Number">${skip_count}</Data></Cell>
      </Row>
      <Row/>

      <!-- Kolon başlıkları -->
      <Row>
        <Cell ss:StyleID="header"><Data ss:Type="String">Sıra</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">E-posta</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">Durum</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">Detay / Hata Mesajı</Data></Cell>
      </Row>

      <!-- Veri satırları -->
      ${dataRows}
    </Table>
  </Worksheet>
</Workbook>`;

    const blob = new Blob([xml], { type: 'application/vnd.ms-excel;charset=utf-8;' });
    _downloadBlob(blob, filename + '.xls');
}

/** Blob'u tarayıcıda indir */
function _downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a   = document.createElement('a');
    a.href     = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 1000);
}

window.exportBulkLog = exportBulkLog;
window._bulkFetchWithRetry = _bulkFetchWithRetry;

/* ══════════════════════════════════════════════════════════════
   METIN YAPISTIR KAYNAGI — Paste modunda toplu gönderim
   Her satırı bir e-posta adresi olarak okur.
   Ayraç beklenmez — sadece satır sonu (newline) kullanılır.
   ══════════════════════════════════════════════════════════════ */

/**
 * Textarea'daki e-posta sayısını anlık günceller.
 * Her tuş vuruşunda (oninput) çağrılır.
 */
function updatePasteCount() {
    const ta = document.getElementById('b-paste-emails');
    const countEl = document.getElementById('b-paste-count');
    if (!ta || !countEl) return;
    // Satırları ayır, boşlukları temizle, geçerli görünenleri say
    const lines = ta.value.split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0 && l.includes('@'));
    countEl.textContent = lines.length > 0 ? `${lines.length} adres` : '';
}

/**
 * Textarea içeriğini temizler.
 */
function clearPasteList() {
    const ta = document.getElementById('b-paste-emails');
    if (ta) { ta.value = ''; updatePasteCount(); }
}

/**
 * Tekrar eden e-posta adreslerini kaldırır ve listeyi sıralar.
 * Büyük/küçük harf farkı gözetmeksizin karşılaştırır.
 */
function deduplicatePasteList() {
    const ta = document.getElementById('b-paste-emails');
    if (!ta) return;
    const lines = ta.value.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    const seen  = new Set();
    const unique = [];
    for (const line of lines) {
        const key = line.toLowerCase();
        if (!seen.has(key)) { seen.add(key); unique.push(line); }
    }
    const removed = lines.length - unique.length;
    ta.value = unique.join('\n');
    updatePasteCount();
    if (removed > 0) showAlert('b-alert', `✅ ${removed} tekrar eden adres kaldırıldı.`, 'ok');
}

/**
 * Yapıştırılmış metin listesinden toplu gönderim başlatır.
 * Her satır bir e-posta adresi olarak işlenir.
 * Boş satırlar ve @ içermeyenler sessizce atlanır.
 * Gönderim: /api/send-bulk endpoint'i — tek tek mail gönderir.
 * Liste geçici olarak bir FormData array'ine dönüştürülür;
 * sunucu tarafında 'paste_emails' anahtarından okunur.
 */
async function startBulkFromPaste() {
    const ta = document.getElementById('b-paste-emails');
    if (!ta || !ta.value.trim()) {
        showAlert('b-alert', 'Lütfen e-posta adresi yapıştırın.', 'err');
        return;
    }

    // Satır satır ayır, boş ve geçersiz formatları çıkar
    const emails = ta.value.split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0 && l.includes('@'));

    if (emails.length === 0) {
        showAlert('b-alert', 'Geçerli e-posta adresi bulunamadı. Her satıra bir adres yazın.', 'err');
        return;
    }

    // Ortak alanları doğrula
    const sid  = document.getElementById('b-sender').value;
    const subj = document.getElementById('b-subject').value.trim();
    const body = document.getElementById('b-body').value.trim();
    if (!sid || !subj || !body) {
        showAlert('b-alert', 'Gönderici, konu ve mesaj zorunludur.', 'err');
        return;
    }

    // UI hazırla
    const btn    = document.getElementById('b-send-btn');
    const sp     = document.getElementById('b-sp');
    const btxt   = document.getElementById('b-btn-txt');
    const stopBtn = document.getElementById('b-stop-btn');
    btn.disabled = true; sp.style.display = 'block';
    btxt.textContent = 'Gönderiliyor...';
    if (stopBtn) stopBtn.style.display = 'inline-flex';
    hideAlert('b-alert');
    document.getElementById('b-prog-wrap').style.display = 'block';
    document.getElementById('b-log').innerHTML = '';
    ['b-ok','b-err','b-skip','b-tot'].forEach(id => {
        const el = document.getElementById(id); if (el) el.textContent = '0';
    });
    const fill = document.getElementById('b-fill');
    if (fill) fill.style.width = '0%';

    window._bulkAbort   = new AbortController();
    window._bulkStopped = false;

    // FormData oluştur — e-posta listesini JSON olarak gönder
    const fd = new FormData();
    fd.append('sender_id',          sid);
    fd.append('rule_id',            document.getElementById('b-rule').value || '');
    fd.append('paste_emails',       JSON.stringify(emails));  // Sunucu bu anahtardan okur
    fd.append('subject',            subj);
    fd.append('body',               body);
    fd.append('html_mode',          document.getElementById('b-html').checked ? 'true' : 'false');
    fd.append('include_unsubscribe',document.getElementById('b-unsub') && document.getElementById('b-unsub').checked ? 'true' : 'false');
    fd.append('mx_check',           document.getElementById('b-mx-check') && document.getElementById('b-mx-check').checked ? 'true' : 'false');
    fd.append('delay_ms',           document.getElementById('b-delay').value);
    fd.append('source',             'paste');  // Backend'e kaynak tipini bildir

    // Toplu gönderim sayısını başlık olarak göster
    const titleEl = document.getElementById('b-prog-title');
    if (titleEl) titleEl.textContent = `Gönderim Durumu (${emails.length} adres)`;

    try {
        const partOk = await _bulkFetchWithRetry('/api/send-bulk', fd);
        if (!partOk && !window._bulkStopped) {
            showAlert('b-alert', 'Gönderim tamamlanamadı.', 'err');
        }
    } catch(e) {
        if (!window._bulkStopped) showAlert('b-alert', 'Bağlantı hatası: ' + e, 'err');
    }

    // UI sıfırla
    btn.disabled = false; sp.style.display = 'none';
    btxt.textContent = '🚀 Toplu Gönderimi Başlat';
    if (stopBtn) stopBtn.style.display = 'none';
    window._bulkStopped = false;
}

window.updatePasteCount    = updatePasteCount;
window.clearPasteList      = clearPasteList;
window.deduplicatePasteList = deduplicatePasteList;
