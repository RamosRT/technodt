/* TSD Screens — feature views composed from components */

const { useState: uS } = React;

// Sample data
const SAMPLE_DOCS = [
  { id: 1, kind: 'УПД',           number: '8841', date: '02.05.2026', barcode: '6418371840293841' },
  { id: 2, kind: 'УПД',           number: '8842', date: '02.05.2026', barcode: '6418371840293842' },
  { id: 3, kind: 'Перемещение',   number: '0427', date: '02.05.2026', barcode: '6418371840293843' },
  { id: 4, kind: 'Счёт-фактура',  number: 'СФ-114', date: '02.05.2026', barcode: '6418371840293844' },
  { id: 5, kind: 'УПД',           number: '8845', date: '02.05.2026', barcode: '6418371840293845' },
];

// ── HOME ──────────────────────────────────────────────────────────
function HomeScreen({ operator, onNav }) {
  return (
    <>
      <AppBar
        title="ТехноКонверт"
        subtitle={operator}
        right={<button className="iconbtn" onClick={() => onNav('service')}><Icon name="settings-2" size={20} /></button>}
      />
      <ConnBanner kind="ok" />
      <div className="tsd-body">
        <div className="tsd-section">
          <div className="tsd-section-title">Действия</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Tile icon="package-plus" title="Новый конверт" subtitle="Регистрация" onClick={() => onNav('register')} />
            <Tile icon="scan-line" title="Проверить" subtitle="Верификация" alt onClick={() => onNav('verify')} />
          </div>
        </div>
        <div className="tsd-section" style={{ paddingTop: 4 }}>
          <div className="tsd-section-title">Последние</div>
          <div className="t-list" style={{ borderRadius: 10, border: '1px solid var(--border-soft)', overflow: 'hidden' }}>
            <div className="t-row" onClick={() => onNav('register')}>
              <div className="leading warning"><Icon name="package" size={18} /></div>
              <div className="body">
                <div className="title">ТА-7461829305184729</div>
                <div className="sub"><StatusPill status="sealed" /> · 12 док. · сегодня 14:31</div>
              </div>
              <div className="trail"><Icon name="chevron-right" size={16} /></div>
            </div>
            <div className="t-row">
              <div className="leading success"><Icon name="package-check" size={18} /></div>
              <div className="body">
                <div className="title">ТА-7461829305184612</div>
                <div className="sub"><StatusPill status="verified" /> · 8 док. · вчера 17:02</div>
              </div>
              <div className="trail"><Icon name="chevron-right" size={16} /></div>
            </div>
            <div className="t-row">
              <div className="leading danger"><Icon name="package-x" size={18} /></div>
              <div className="body">
                <div className="title">ТА-7461829305184528</div>
                <div className="sub"><StatusPill status="discrepancy" /> · 1 не найден</div>
              </div>
              <div className="trail"><Icon name="chevron-right" size={16} /></div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ── REGISTER ──────────────────────────────────────────────────────
function RegisterScreen({ onBack, onPrint }) {
  const [docs, setDocs] = uS(SAMPLE_DOCS.slice(0, 3));
  const [toast, setToast] = uS('');
  const [showSeal, setShowSeal] = uS(false);
  const [sealed, setSealed] = uS(false);

  function addNext() {
    if (docs.length >= SAMPLE_DOCS.length) { setToast('Все документы добавлены'); return; }
    setDocs([...docs, SAMPLE_DOCS[docs.length]]);
    setToast('Добавлен');
  }

  return (
    <>
      <AppBar title="Регистрация" subtitle={sealed ? 'Конверт запечатан' : 'Сканируйте документы'} onBack={onBack}
              right={!sealed && <button className="iconbtn" onClick={addNext}><Icon name="scan-line" size={20} /></button>} />
      <div className="tsd-body" style={{ paddingBottom: 0 }}>
        <EnvelopeHero
          number="ТА-7461829305184729"
          status={sealed ? 'sealed' : 'draft'}
          docCount={docs.length}
          sender="Иван Петров"
          branch="Москва, скл. №3"
        />
        {!sealed && <ScanTarget label="Готов к сканированию" hint={`${docs.length} в конверте · сканируйте следующий`} />}

        <div className="tsd-section">
          <div className="tsd-section-title">Документы в конверте</div>
          <div style={{ background: '#fff', borderRadius: 10, border: '1px solid var(--border-soft)', overflow: 'hidden' }}>
            {docs.length === 0 && <Empty icon="package-open" title="Конверт пуст" desc="Отсканируйте первый документ" />}
            {docs.map((d, i) => (
              <DocRow key={d.id} idx={i + 1} kind={d.kind} number={d.number} date={d.date}
                      status={sealed ? null : 'editable'}
                      onRemove={() => setDocs(docs.filter(x => x.id !== d.id))} />
            ))}
          </div>
        </div>

        {sealed && (
          <div className="tsd-section">
            <div className="tsd-section-title">Печать</div>
            <button className="t-btn t-btn-tonal t-btn-md" style={{ width: '100%', marginBottom: 6 }} onClick={onPrint}>
              <Icon name="printer" size={18} /> Этикетка ZPL · TLP-300 склад
            </button>
            <button className="t-btn t-btn-ghost t-btn-md" style={{ width: '100%' }}>
              <Icon name="file-text" size={18} /> Опись (печать с ПК)
            </button>
          </div>
        )}
      </div>
      <div className="tsd-bottombar">
        {!sealed ? (
          <>
            <button className="t-btn t-btn-ghost t-btn-cta" style={{ flex: '0 0 auto', minWidth: 0, padding: '0 14px' }} onClick={onBack}>
              <Icon name="x" size={18} />
            </button>
            <button className="t-btn t-btn-primary t-btn-cta" disabled={docs.length === 0} onClick={() => setShowSeal(true)}>
              <Icon name="package-check" size={18} /> Запечатать
            </button>
          </>
        ) : (
          <button className="t-btn t-btn-success t-btn-cta" onClick={onBack}>
            <Icon name="check" size={18} /> Готово
          </button>
        )}
      </div>
      <Toast msg={toast} kind="success" onHide={() => setToast('')} />

      <BottomSheet open={showSeal} onClose={() => setShowSeal(false)}
                   title="Запечатать конверт" desc="Выберите подписанта и филиал-отправитель. Состав будет заморожен.">
        <div className="t-field">
          <label>Подписант-отправитель</label>
          <select className="t-select"><option>Петров И.А.</option><option>Сидоров А.К.</option></select>
        </div>
        <div className="t-field">
          <label>Подписант-получатель</label>
          <select className="t-select"><option>— выберите —</option><option>Иванова О.С.</option></select>
        </div>
        <div className="t-field">
          <label>Филиал-отправитель</label>
          <select className="t-select"><option>Москва, склад №3</option></select>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
          <button className="t-btn t-btn-ghost t-btn-md" style={{ flex: 1 }} onClick={() => setShowSeal(false)}>Отмена</button>
          <button className="t-btn t-btn-primary t-btn-md" style={{ flex: 2 }}
                  onClick={() => { setShowSeal(false); setSealed(true); setToast('Конверт запечатан'); }}>
            <Icon name="package-check" size={16} /> Запечатать
          </button>
        </div>
      </BottomSheet>
    </>
  );
}

// ── VERIFY ────────────────────────────────────────────────────────
function VerifyScreen({ onBack }) {
  const allDocs = SAMPLE_DOCS;
  const [scanned, setScanned] = uS([1, 2]);
  const [toast, setToast] = uS({ msg: '', kind: 'success' });
  const [done, setDone] = uS(false);

  function scanNext() {
    const next = allDocs.find(d => !scanned.includes(d.id));
    if (!next) { setToast({ msg: 'Все документы отсканированы', kind: 'success' }); return; }
    setScanned([...scanned, next.id]);
    setToast({ msg: `Отсканирован: ${next.kind} ${next.number}`, kind: 'success' });
  }
  function scanWrong() { setToast({ msg: 'Документ не из этого конверта', kind: 'danger' }); }

  const all = scanned.length === allDocs.length;

  return (
    <>
      <AppBar title="Верификация" subtitle={`${scanned.length}/${allDocs.length} отсканировано`} onBack={onBack}
              right={<>
                <button className="iconbtn" onClick={scanWrong}><Icon name="circle-x" size={20} /></button>
                <button className="iconbtn" onClick={scanNext}><Icon name="scan-line" size={20} /></button>
              </>} />
      <div className="tsd-body" style={{ paddingBottom: 0 }}>
        <EnvelopeHero
          number="ТА-7461829305184612"
          status={done ? (all ? 'verified' : 'discrepancy') : 'sealed'}
          docCount={allDocs.length}
          scannedCount={scanned.length}
          sender="Анна Соколова"
        />
        {!done && <ScanTarget label={all ? 'Все отсканированы' : 'Сканируйте следующий документ'}
                              hint={all ? 'Можно завершить' : `Осталось ${allDocs.length - scanned.length}`} armed={!all} />}

        <div className="tsd-section">
          <div className="tsd-section-title">Состав конверта</div>
          <div style={{ background: '#fff', borderRadius: 10, border: '1px solid var(--border-soft)', overflow: 'hidden' }}>
            {allDocs.map((d, i) => (
              <DocRow key={d.id} idx={i + 1} kind={d.kind} number={d.number} date={d.date}
                      status={scanned.includes(d.id) ? 'scanned' : 'pending'} />
            ))}
          </div>
        </div>
      </div>
      <div className="tsd-bottombar">
        {done ? (
          <button className="t-btn t-btn-success t-btn-cta" onClick={onBack}><Icon name="check" size={18} /> Готово</button>
        ) : all ? (
          <button className="t-btn t-btn-success t-btn-cta" onClick={() => { setDone(true); setToast({ msg: 'Сверка завершена', kind: 'success' }); }}>
            <Icon name="check" size={18} /> Завершить сверку
          </button>
        ) : (
          <>
            <button className="t-btn t-btn-ghost t-btn-cta" style={{ flex: '0 0 auto', padding: '0 14px' }} onClick={onBack}>
              <Icon name="x" size={18} />
            </button>
            <button className="t-btn t-btn-danger t-btn-cta"
                    onClick={() => { setDone(true); setToast({ msg: 'Завершено с расхождением', kind: 'danger' }); }}>
              <Icon name="triangle-alert" size={18} /> С расхождением
            </button>
          </>
        )}
      </div>
      <Toast msg={toast.msg} kind={toast.kind} onHide={() => setToast({ msg: '', kind: 'success' })} />
    </>
  );
}

// ── SERVICE MENU ──────────────────────────────────────────────────
function ServiceScreen({ onBack, operator, onLogout, onPrinter }) {
  const [showBranch, setShowBranch] = uS(false);
  const [showSender, setShowSender] = uS(false);
  const [branch, setBranch] = uS('Москва, склад №3');
  const [sender, setSender] = uS('Петров И.А.');
  const branches = ['Москва, склад №3', 'Санкт-Петербург, центр', 'Новосибирск, ул. Ленина 41', 'Екатеринбург, склад №1'];
  const senders = ['Петров И.А.', 'Сидоров А.К.', 'Иванова О.С.'];

  return (
    <>
      <AppBar title="Сервисное меню" onBack={onBack} />
      <div className="tsd-body">
        <div className="tsd-section">
          <div className="tsd-section-title">Учётная запись</div>
          <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border-soft)' }}>
            <ServiceRow icon="circle-user" title="Оператор" value={operator} trail={null} />
            <ServiceRow icon="log-out" title="Выйти" trail="chevron-right" onClick={onLogout} />
          </div>
        </div>
        <div className="tsd-section">
          <div className="tsd-section-title">Предпочтения отправки</div>
          <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border-soft)' }}>
            <ServiceRow icon="building-2" title="Филиал-отправитель" value={branch} onClick={() => setShowBranch(true)} />
            <ServiceRow icon="user-round" title="Подписант-отправитель" value={sender} onClick={() => setShowSender(true)} />
          </div>
        </div>
        <div className="tsd-section">
          <div className="tsd-section-title">Печать</div>
          <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border-soft)' }}>
            <ServiceRow icon="printer" title="Термопринтер ZPL" value="TLP-300 · 192.168.1.42" onClick={onPrinter} />
          </div>
        </div>
        <div className="tsd-section">
          <div className="tsd-section-title">Об устройстве</div>
          <div style={{ borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border-soft)' }}>
            <ServiceRow icon="smartphone" title="ТСД" value="Urovo DT40 · serial 0184" trail={null} />
            <ServiceRow icon="info" title="Версия" value="1.2.0 · build 184" trail={null} />
          </div>
        </div>
      </div>

      <BottomSheet open={showBranch} onClose={() => setShowBranch(false)} title="Филиал-отправитель" desc="Подставится по умолчанию при создании конверта.">
        <div style={{ marginLeft: -16, marginRight: -16, marginBottom: 4 }}>
          {branches.map(b => (
            <div key={b} className="t-srow" onClick={() => { setBranch(b); setShowBranch(false); }}
                 style={{ background: branch === b ? 'var(--surface-tint)' : '#fff' }}>
              <i data-lucide="building-2" className="lucide-lead" />
              <div className="body"><div className="ttl">{b}</div></div>
              {branch === b && <i data-lucide="check" className="lucide-trail" style={{ color: 'var(--brand-blue)' }} />}
            </div>
          ))}
        </div>
      </BottomSheet>
      <BottomSheet open={showSender} onClose={() => setShowSender(false)} title="Подписант-отправитель">
        <div style={{ marginLeft: -16, marginRight: -16, marginBottom: 4 }}>
          {senders.map(s => (
            <div key={s} className="t-srow" onClick={() => { setSender(s); setShowSender(false); }}
                 style={{ background: sender === s ? 'var(--surface-tint)' : '#fff' }}>
              <i data-lucide="user-round" className="lucide-lead" />
              <div className="body"><div className="ttl">{s}</div></div>
              {sender === s && <i data-lucide="check" className="lucide-trail" style={{ color: 'var(--brand-blue)' }} />}
            </div>
          ))}
        </div>
      </BottomSheet>
    </>
  );
}

// ── PRINTER PICKER ────────────────────────────────────────────────
function PrinterScreen({ onBack }) {
  const [sel, setSel] = uS('TLP-300-1');
  const printers = [
    { id: 'TLP-300-1', name: 'TLP-300 склад',   ip: '192.168.1.42', proto: 'ZPL · 203 dpi', here: true },
    { id: 'TLP-300-2', name: 'TLP-300 офис',     ip: '192.168.1.43', proto: 'ZPL · 203 dpi', here: false },
    { id: 'ZD230',     name: 'Zebra ZD230',      ip: '192.168.1.51', proto: 'ZPL · 203 dpi', here: false },
  ];
  return (
    <>
      <AppBar title="Принтер этикеток" subtitle="Сетевой ZPL" onBack={onBack}
              right={<button className="iconbtn"><Icon name="rotate-cw" size={20} /></button>} />
      <ConnBanner kind="ok" label="3 принтера в локальной сети" />
      <div className="tsd-body">
        <div className="tsd-section">
          <div className="tsd-section-title">Доступные принтеры</div>
          {printers.map(p => (
            <div key={p.id} className={`t-printer-row ${sel === p.id ? 'selected' : ''}`} onClick={() => setSel(p.id)}>
              <div className="ico"><Icon name="printer" size={18} /></div>
              <div className="body">
                <div className="ttl">{p.name}</div>
                <div className="sub">{p.ip} · {p.proto}</div>
              </div>
              {sel === p.id && <Icon name="check" size={18} style={{ color: 'var(--brand-blue)' }} />}
            </div>
          ))}
        </div>
        <div className="tsd-section">
          <div className="tsd-section-title">Параметры этикетки</div>
          <div className="t-field">
            <label>Размер</label>
            <select className="t-select"><option>58 × 40 мм</option><option>100 × 50 мм</option></select>
          </div>
          <div className="t-field">
            <label>Копий</label>
            <select className="t-select"><option>1</option><option>2</option></select>
          </div>
          <button className="t-btn t-btn-tonal t-btn-md" style={{ width: '100%' }}>
            <Icon name="printer-check" size={18} /> Печать тестовой этикетки
          </button>
        </div>
      </div>
      <div className="tsd-bottombar">
        <button className="t-btn t-btn-primary t-btn-cta" onClick={onBack}><Icon name="check" size={18} /> Сохранить</button>
      </div>
    </>
  );
}

Object.assign(window, { HomeScreen, RegisterScreen, VerifyScreen, ServiceScreen, PrinterScreen });
