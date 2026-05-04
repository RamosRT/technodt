/* Reusable TSD components — load after styles.css */

const { useState, useEffect, useRef, useMemo } = React;

// ── Lucide icon helper ────────────────────────────────────────────
function Icon({ name, size, style }) {
  const ref = useRef(null);
  useEffect(() => {
    if (window.lucide && ref.current) window.lucide.createIcons({ icons: window.lucide.icons, attrs: {}, nameAttr: 'data-lucide', root: ref.current });
  }, [name]);
  return <i ref={ref} data-lucide={name} className="lucide" style={{ width: size, height: size, ...style }} />;
}

// ── Status bar (Android-mini) ─────────────────────────────────────
function StatusBar({ time = '14:31' }) {
  return (
    <div className="tsd-statusbar">
      <span>{time}</span>
      <div className="right">
        <Icon name="wifi" size={11} />
        <Icon name="battery-medium" size={12} />
        <span style={{ fontSize: 9 }}>78%</span>
      </div>
    </div>
  );
}

// ── App bar ───────────────────────────────────────────────────────
function AppBar({ title, subtitle, onBack, right }) {
  return (
    <div className="tsd-appbar">
      {onBack ? (
        <button className="iconbtn" onClick={onBack}><Icon name="arrow-left" size={20} /></button>
      ) : <div style={{ width: 12 }} />}
      <div className="title">
        {title}
        {subtitle && <small>{subtitle}</small>}
      </div>
      <div className="right">{right}</div>
    </div>
  );
}

// ── Connection banner ─────────────────────────────────────────────
function ConnBanner({ kind = 'ok', label }) {
  const map = { ok: { cls: '', icon: 'wifi', text: label || 'Сеть · 1С · Принтер готовы' },
                warn: { cls: 'warn', icon: 'wifi-low', text: label || 'Слабый сигнал' },
                error: { cls: 'error', icon: 'wifi-off', text: label || 'Нет связи с сервером' } }[kind];
  return <div className={`t-conn ${map.cls}`}><Icon name={map.icon} size={12} /><span>{map.text}</span></div>;
}

// ── Status pill ───────────────────────────────────────────────────
const STATUS_LABEL = { draft: 'Черновик', sealed: 'Запечатан', verified: 'Сверен', discrepancy: 'С расхождением' };
function StatusPill({ status, onDark }) {
  return (
    <span className={`t-pill t-pill-${status}`} style={onDark ? { background: 'rgba(255,255,255,.18)', color: '#fff' } : null}>
      <span className="dot" style={onDark ? { background: '#fff' } : null} />
      {STATUS_LABEL[status] || status}
    </span>
  );
}

// ── Hero (envelope summary on dark gradient) ──────────────────────
function EnvelopeHero({ number, status, docCount, scannedCount, sender, branch }) {
  return (
    <div className="t-hero">
      <div className="row">
        <StatusPill status={status} onDark />
        <span style={{ marginLeft: 'auto', fontSize: 10, opacity: .65, fontFamily: 'var(--font-mono)' }}>Code128</span>
      </div>
      <div className="num">{number}</div>
      <div className="meta">
        <div><b>{docCount}</b>документов</div>
        {scannedCount != null && <div><b>{scannedCount}/{docCount}</b>отсканировано</div>}
        {sender && <div><b style={{ fontSize: 12 }}>{sender}</b>отправитель</div>}
        {branch && <div><b style={{ fontSize: 12 }}>{branch}</b>филиал</div>}
      </div>
    </div>
  );
}

// ── Scan target ───────────────────────────────────────────────────
function ScanTarget({ label = 'Готов к сканированию', hint = 'Наведите сканер на штрихкод', armed = true }) {
  return (
    <div className={`t-scan ${armed ? 'armed' : ''}`}>
      <div className="scan-icon"><Icon name="scan-line" size={22} /></div>
      <div style={{ flex: 1 }}>
        <div className="label">{label}</div>
        <div className="hint">{hint}</div>
      </div>
    </div>
  );
}

// ── Doc row ───────────────────────────────────────────────────────
function DocRow({ idx, kind, number, date, status, onRemove }) {
  return (
    <div className={`t-doc-row ${status === 'scanned' ? 'scanned' : ''} ${status === 'pending' ? 'pending' : ''}`}>
      <div className="num">{idx}</div>
      <div className="ico"><Icon name="file-text" size={13} /></div>
      <div className="body">
        <div className="ttl"><span className="kind">{kind}</span> №{number}</div>
        <div className="meta">{date}</div>
      </div>
      {status === 'scanned' && <div className="check"><Icon name="check-circle-2" size={18} /></div>}
      {status === 'pending' && <div className="check pending"><Icon name="circle" size={18} /></div>}
      {status === 'editable' && onRemove && <button className="remove" onClick={onRemove}><Icon name="x" size={16} /></button>}
    </div>
  );
}

// ── Tile ──────────────────────────────────────────────────────────
function Tile({ icon, title, subtitle, onClick, alt }) {
  return (
    <div className={`t-tile ${alt ? 'alt' : ''}`} onClick={onClick}>
      <div className="icon-wrap"><Icon name={icon} size={22} /></div>
      <div>
        <div className="ttl">{title}</div>
        <div className="sub">{subtitle}</div>
      </div>
    </div>
  );
}

// ── Toast ─────────────────────────────────────────────────────────
function Toast({ msg, kind = 'success', onHide }) {
  useEffect(() => { if (msg) { const t = setTimeout(onHide, 2400); return () => clearTimeout(t); } }, [msg]);
  if (!msg) return null;
  const icon = kind === 'success' ? 'check-circle-2' : kind === 'danger' ? 'circle-x' : 'info';
  return <div className={`t-toast ${kind}`}><Icon name={icon} size={18} /><span>{msg}</span></div>;
}

// ── Service row ───────────────────────────────────────────────────
function ServiceRow({ icon, title, value, onClick, trail = 'chevron-right' }) {
  return (
    <div className="t-srow" onClick={onClick}>
      <i data-lucide={icon} className="lucide-lead" />
      <div className="body">
        <div className="ttl">{title}</div>
        {value && <div className="val">{value}</div>}
      </div>
      {trail && <i data-lucide={trail} className="lucide-trail" />}
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────
function Empty({ icon, title, desc }) {
  return (
    <div className="t-empty">
      <div className="ico"><Icon name={icon} size={26} /></div>
      <div className="ttl">{title}</div>
      <div className="desc">{desc}</div>
    </div>
  );
}

// ── Bottom sheet ──────────────────────────────────────────────────
function BottomSheet({ open, onClose, title, desc, children }) {
  if (!open) return null;
  return (
    <div className="t-overlay" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="t-sheet">
        <div className="grab" />
        {title && <div className="ttl">{title}</div>}
        {desc && <div className="desc">{desc}</div>}
        {children}
      </div>
    </div>
  );
}

// ── Login ─────────────────────────────────────────────────────────
function LoginScreen({ onLogin }) {
  const [name, setName] = useState('');
  const [pwd, setPwd] = useState('');
  return (
    <div className="t-login">
      <div className="logo">
        <img className="logo-lockup" src="../../assets/logo-lockup.png" alt="ТехноКонверт" />
        <div className="tagline">Учёт передачи документов · ТСД</div>
      </div>
      <div className="t-field">
        <label>Имя оператора</label>
        <input className="t-input" value={name} onChange={e => setName(e.target.value)} placeholder="ivan.petrov" />
      </div>
      <div className="t-field">
        <label>Пароль</label>
        <input type="password" className="t-input password" value={pwd} onChange={e => setPwd(e.target.value)} placeholder="••••" />
      </div>
      <button className="t-btn t-btn-primary t-btn-cta" style={{ marginTop: 8 }} onClick={() => onLogin(name || 'Иван Петров')} disabled={!name || !pwd}>Войти</button>
      <div className="device-strip">
        <Icon name="smartphone" size={14} />
        <span>Устройство:</span>
        <b style={{ color: 'var(--fg-1)', fontWeight: 500 }}>Urovo DT40 · DataWedge</b>
      </div>
      <div style={{ marginTop: 'auto', textAlign: 'center', fontSize: 10, color: 'var(--fg-4)', fontFamily: 'var(--font-mono)' }}>v1.2.0 · build 184</div>
    </div>
  );
}

// Export to window
Object.assign(window, {
  Icon, StatusBar, AppBar, ConnBanner, StatusPill, EnvelopeHero,
  ScanTarget, DocRow, Tile, Toast, ServiceRow, Empty, BottomSheet, LoginScreen,
  STATUS_LABEL,
});
