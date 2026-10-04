'use strict'

/* ============================================================
   データ — 表示する数字はすべてこのデータから導出する(偽の数字禁止)
   ============================================================ */
const INITIAL_DEALS = [
  {
    id: 'd1',
    property: '練馬区 一棟マンション',
    price: 23048,
    yield: 7.2,
    customer: '田中様',
    email: 'tanaka@example.com',
    status: 'active',
    priority: true
  },
  {
    id: 'd2',
    property: '川口市 一棟アパート',
    price: 9800,
    yield: 8.1,
    customer: '佐藤様',
    email: 'sato@example',
    status: 'active',
    priority: true
  },
  {
    id: 'd3',
    property: '横浜市 区分レジ2戸',
    price: 6480,
    yield: 6.8,
    customer: '鈴木様',
    email: 'suzuki@example.com',
    status: 'active',
    priority: true
  },
  {
    id: 'd4',
    property: '板橋区 一棟マンション',
    price: 31200,
    yield: 6.5,
    customer: '高橋様',
    email: '',
    status: 'active',
    priority: false
  },
  {
    id: 'd5',
    property: '船橋市 一棟アパート',
    price: 7350,
    yield: 8.4,
    customer: '伊藤様',
    email: 'ito@example.com',
    status: 'closed',
    priority: false
  }
]

const STATUS_LABELS = {
  active: { label: '進行中', className: 'badge-active' },
  done: { label: '成約', className: 'badge-done' },
  closed: { label: '売却済', className: 'badge-closed' },
  dropped: { label: '取下げ', className: 'badge-dropped' }
}

/* 状態はすべてイミュータブルに扱う */
let state = {
  deals: INITIAL_DEALS,
  selected: INITIAL_DEALS.filter((d) => d.priority && d.email !== '').map((d) => d.id),
  fixups: [],
  sending: false
}

function setState(patch) {
  state = { ...state, ...patch }
  renderList()
}

/* ============================================================
   ヘルパー
   ============================================================ */
/* テーブルは「生数値+3桁カンマ」のみ。単位は列ヘッダーが持つ(1列1単位) */
const NUM_FORMAT = new Intl.NumberFormat('ja-JP')

function formatMan(man) {
  if (man == null) return '—'
  return NUM_FORMAT.format(man)
}

/* 大型表示用: カンマを減光する(.num-sep) */
function formatManDisplay(man) {
  return formatMan(man).replace(/,/g, '<span class="num-sep">,</span>')
}

function formatYield(y) {
  return y == null ? '—' : y.toFixed(1)
}

function isSendable(deal) {
  return deal.status === 'active' && deal.email !== ''
}

function excludeReason(deal) {
  if (deal.status !== 'active') return `${STATUS_LABELS[deal.status].label}のため対象外`
  if (deal.email === '') return 'メール未入力のため対象外'
  return null
}

/* ============================================================
   ナビゲーション(1画面1目的)
   ============================================================ */
const views = { home: 'view-home', list: 'view-list', report: 'view-report' }

function navigate(key) {
  Object.entries(views).forEach(([k, id]) => {
    document.getElementById(id).hidden = k !== key
  })
  document.querySelectorAll('.app-nav [data-nav], .side-nav [data-nav], .bottom-tabs [data-nav]').forEach((btn) => {
    if (btn.dataset.nav === key) {
      btn.setAttribute('aria-current', 'page')
    } else {
      btn.removeAttribute('aria-current')
    }
  })
  window.scrollTo({ top: 0 })
  if (key === 'report') animateBars()
}

document.querySelectorAll('[data-nav]').forEach((btn) => {
  btn.addEventListener('click', () => navigate(btn.dataset.nav))
})

/* ============================================================
   ホーム: 最近の動き(スケルトン → 実データ)
   ============================================================ */
const RECENT = [
  { title: '鈴木様に「横浜市 区分レジ2戸」を提案しました', time: '今日 9:12' },
  { title: '「板橋区 一棟マンション」を概要書から登録しました', time: '昨日 17:40' },
  { title: '伊藤様の「船橋市 一棟アパート」が売却済になりました', time: '7月16日' }
]

function loadRecent() {
  const el = document.getElementById('recent-activity')
  window.setTimeout(() => {
    el.innerHTML = RECENT.map(
      (r) => `
      <div class="card-row">
        <div class="row-main"><div class="todo-row-title" style="font-weight:400">${r.title}</div></div>
        <div class="todo-row-sub tnum">${r.time}</div>
      </div>`
    ).join('')
  }, 900)
}

/* ============================================================
   提案リスト: 事前選択 + 要入力の自動除外 + 一括送信
   ============================================================ */
function renderList() {
  const tbody = document.getElementById('deal-rows')
  tbody.innerHTML = state.deals
    .map((deal) => {
      const sendable = isSendable(deal)
      const reason = excludeReason(deal)
      const checked = state.selected.includes(deal.id)
      const st = STATUS_LABELS[deal.status]
      return `
      <tr class="${sendable ? '' : 'row-excluded'}">
        <td>
          <input type="checkbox" data-deal="${deal.id}" ${checked ? 'checked' : ''} ${sendable ? '' : 'disabled'}
            aria-label="${deal.property}を選択">
        </td>
        <td>
          <div style="font-weight:600">${deal.property}</div>
          ${reason ? `<div class="todo-row-sub">${reason}</div>` : ''}
        </td>
        <td>
          <div>${deal.customer}</div>
          ${deal.email === '' ? '<span class="badge badge-alert">要入力</span>' : `<div class="todo-row-sub">${deal.email}</div>`}
        </td>
        <td class="col-num num">${formatMan(deal.price)}</td>
        <td class="col-num num">${formatYield(deal.yield)}</td>
        <td><span class="badge ${st.className}">${st.label}</span></td>
      </tr>`
    })
    .join('')

  /* SP用: 同じ状態から「主要3項目(物件・価格・状態)」のカードを描画(情報削減) */
  const cards = document.getElementById('deal-cards')
  cards.innerHTML = state.deals
    .map((deal) => {
      const sendable = isSendable(deal)
      const reason = excludeReason(deal)
      const checked = state.selected.includes(deal.id)
      const st = STATUS_LABELS[deal.status]
      return `
      <div class="deal-card ${sendable ? '' : 'is-excluded'}">
        <input type="checkbox" data-deal="${deal.id}" ${checked ? 'checked' : ''} ${sendable ? '' : 'disabled'}
          aria-label="${deal.property}を選択" style="margin-top:2px">
        <div class="dc-main">
          <div class="dc-title">${deal.property}</div>
          <div class="dc-sub">${deal.customer}${reason ? ` ・ ${reason}` : ''}</div>
        </div>
        <div class="dc-right">
          <div class="dc-price">${formatManDisplay(deal.price)}<span class="unit">万円</span></div>
          <span class="badge ${st.className}">${st.label}</span>
        </div>
      </div>`
    })
    .join('')

  document.querySelectorAll('#deal-rows input[type="checkbox"], #deal-cards input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener('change', () => {
      const id = cb.dataset.deal
      const next = cb.checked
        ? [...state.selected, id]
        : state.selected.filter((s) => s !== id)
      setState({ selected: next })
    })
  })

  const count = state.selected.length
  document.getElementById('selection-summary').textContent = `${count}件を選択中`

  const btn = document.getElementById('btn-open-confirm')
  btn.textContent = `選択した${count}件の内容を確認する`
  btn.disabled = count === 0 || state.sending

  renderFixups()
}

/* ============================================================
   送信前のその場確認モーダル
   ============================================================ */
const overlay = document.getElementById('confirm-overlay')
let lastFocused = null

function openConfirm() {
  const selectedDeals = state.deals.filter((d) => state.selected.includes(d.id))
  document.getElementById('confirm-title').textContent =
    `この内容で${selectedDeals.length}件に送信します`
  document.getElementById('confirm-recipients').textContent =
    '宛先: ' + selectedDeals.map((d) => `${d.customer}(${d.property})`).join(' / ')
  lastFocused = document.activeElement
  overlay.hidden = false
  document.getElementById('btn-cancel-send').focus()
}

function closeConfirm() {
  overlay.hidden = true
  if (lastFocused) lastFocused.focus()
}

document.getElementById('btn-open-confirm').addEventListener('click', openConfirm)
document.getElementById('btn-cancel-send').addEventListener('click', closeConfirm)

/* 破壊的確認: 外側クリックでは閉じない。ESCは許可 */
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !overlay.hidden) closeConfirm()
})

/* フォーカストラップ(簡易) */
overlay.addEventListener('keydown', (e) => {
  if (e.key !== 'Tab') return
  const focusables = overlay.querySelectorAll('button')
  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault()
    last.focus()
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault()
    first.focus()
  }
})

/* ============================================================
   送信処理: 1件ずつ順に + 進捗表示 + 部分成功
   ============================================================ */
function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

document.getElementById('btn-do-send').addEventListener('click', async () => {
  const sendBtn = document.getElementById('btn-do-send')
  const targets = state.deals.filter((d) => state.selected.includes(d.id))
  setState({ sending: true })

  const results = []
  for (let i = 0; i < targets.length; i += 1) {
    sendBtn.innerHTML = `<span class="spinner" aria-hidden="true"></span>送信中… ${i + 1}/${targets.length}件`
    sendBtn.disabled = true
    await new Promise((resolve) => window.setTimeout(resolve, 800))
    const ok = validateEmail(targets[i].email)
    results.push({ deal: targets[i], ok })
  }

  const okCount = results.filter((r) => r.ok).length
  const failed = results.filter((r) => !r.ok)

  sendBtn.innerHTML = '送信する'
  sendBtn.disabled = false
  closeConfirm()

  setState({
    sending: false,
    selected: [],
    fixups: failed.map((f) => ({
      deal: f.deal,
      reason: `メールアドレスの形式が正しくありません(${f.deal.email})`
    }))
  })

  if (failed.length === 0) {
    showToast({ message: `${okCount}件すべて送信しました` })
  } else {
    showToast({ message: `${okCount}件を送信しました` })
    showToast({
      error: true,
      message: `${failed.length}件が送信できませんでした`,
      sub: 'メールアドレスを修正して再送信できます',
      actionLabel: '確認する',
      onAction: () => {
        document.getElementById('fixup-queue').scrollIntoView({ behavior: 'smooth' })
      }
    })
  }
})

/* ============================================================
   要確認キュー: 失敗分の隔離と回復経路(再試行/修正)
   ============================================================ */
function renderFixups() {
  const heading = document.getElementById('fixup-heading')
  const queue = document.getElementById('fixup-queue')
  const has = state.fixups.length > 0
  heading.hidden = !has
  queue.hidden = !has
  if (!has) return

  heading.innerHTML = `送信できなかった提案 <span class="count">${state.fixups.length}件</span>`
  queue.innerHTML = state.fixups
    .map(
      (f, i) => `
    <div class="card-row" style="flex-wrap:wrap">
      <div class="row-main" style="min-width: 200px">
        <div class="todo-row-title">${f.deal.customer}への送信に失敗しました</div>
        <div class="todo-row-sub">${f.reason}</div>
      </div>
      <div class="field has-error row-grow" style="min-width: 220px">
        <label for="fix-email-${i}">メールアドレス <span class="badge badge-required">必須</span></label>
        <input id="fix-email-${i}" type="email" inputmode="email" value="${f.deal.email}">
        <p class="error-msg">形式を確認してください(例: sato@example.com)</p>
      </div>
      <button type="button" class="btn btn-secondary pressable" data-retry="${i}">修正して再送信</button>
    </div>`
    )
    .join('')

  queue.querySelectorAll('[data-retry]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const i = Number(btn.dataset.retry)
      const input = document.getElementById(`fix-email-${i}`)
      const value = input.value.trim()
      if (!validateEmail(value)) {
        input.focus()
        return
      }
      const fixup = state.fixups[i]
      const nextDeals = state.deals.map((d) =>
        d.id === fixup.deal.id ? { ...d, email: value } : d
      )
      setState({
        deals: nextDeals,
        fixups: state.fixups.filter((_, idx) => idx !== i)
      })
      showToast({ message: `${fixup.deal.customer}に再送信しました` })
    })
  })
}

/* ============================================================
   トースト: 成功は静かに消える / エラーは残す + 次のアクション
   ============================================================ */
function showToast({ message, sub, error = false, actionLabel, onAction }) {
  const region = document.getElementById('toast-region')
  const el = document.createElement('div')
  el.className = `toast pop-in${error ? ' toast-error' : ''}`
  el.innerHTML = `
    <div class="toast-msg">
      <div>${message}</div>
      ${sub ? `<div class="t-sub">${sub}</div>` : ''}
    </div>`
  if (error) {
    const action = document.createElement('button')
    action.type = 'button'
    action.className = 'toast-action'
    action.textContent = actionLabel || '閉じる'
    action.addEventListener('click', () => {
      if (onAction) onAction()
      el.remove()
    })
    el.appendChild(action)
  } else {
    window.setTimeout(() => el.remove(), 4000)
  }
  region.appendChild(el)
}

/* ============================================================
   レポート: バーは表示時にアニメーション(ラベルと数値必須)
   ============================================================ */
function animateBars() {
  document.querySelectorAll('.bar-fill').forEach((bar) => {
    bar.style.width = '0%'
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        bar.style.width = bar.dataset.width
      })
    })
  })
}

/* ============================================================
   物件登録モーダル: 下書き自動保存・復元の可視化・IMEガード
   ============================================================ */
const DRAFT_KEY = 'bukken-desk:register:v1'
const regOverlay = document.getElementById('register-overlay')
const REG_FIELDS = ['reg-name', 'reg-price', 'reg-customer', 'reg-email']
let regLastFocused = null
let draftTimer = null

function readDraft() {
  try {
    return JSON.parse(window.localStorage.getItem(DRAFT_KEY))
  } catch {
    return null
  }
}

function draftValues() {
  return Object.fromEntries(
    REG_FIELDS.map((id) => [id, document.getElementById(id).value])
  )
}

function saveDraft() {
  const values = draftValues()
  const hasContent = Object.values(values).some((v) => v.trim() !== '')
  const status = document.getElementById('draft-status')
  if (!hasContent) {
    window.localStorage.removeItem(DRAFT_KEY)
    status.textContent = ''
    return
  }
  window.localStorage.setItem(DRAFT_KEY, JSON.stringify(values))
  const time = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' })
  status.textContent = `下書きを自動保存しました(${time})`
}

function scheduleDraftSave() {
  window.clearTimeout(draftTimer)
  draftTimer = window.setTimeout(saveDraft, 600)
}

function clearDraft() {
  window.localStorage.removeItem(DRAFT_KEY)
  REG_FIELDS.forEach((id) => {
    document.getElementById(id).value = ''
  })
  document.getElementById('draft-status').textContent = ''
  document.getElementById('draft-note').hidden = true
}

function openRegister() {
  regLastFocused = document.activeElement
  const draft = readDraft()
  const hasDraft = draft && Object.values(draft).some((v) => String(v).trim() !== '')
  if (hasDraft) {
    REG_FIELDS.forEach((id) => {
      document.getElementById(id).value = draft[id] || ''
    })
  }
  /* 復元は黙ってやらない: 通知バー + 破棄ボタン */
  document.getElementById('draft-note').hidden = !hasDraft
  document.getElementById('reg-name-err').hidden = true
  document.getElementById('reg-email-err').hidden = true
  document.getElementById('field-reg-email').classList.remove('has-error')
  regOverlay.hidden = false
  document.getElementById('reg-name').focus()
}

function closeRegister() {
  /* 閉じても下書きは消さない(破棄は明示操作のみ) */
  window.clearTimeout(draftTimer)
  saveDraft()
  regOverlay.hidden = true
  if (regLastFocused) regLastFocused.focus()
}

/* 全角数字・カンマ・スペース入りを受け入れて正規化(ポステルの法則) */
function normalizePrice(raw) {
  const half = raw.replace(/[０-９]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
  const digits = half.replace(/[,，、\s　]/g, '')
  if (digits === '') return null
  const n = Number(digits)
  return Number.isFinite(n) && n > 0 ? Math.round(n) : null
}

function doRegister() {
  const name = document.getElementById('reg-name').value.trim()
  const email = document.getElementById('reg-email').value.trim()
  const nameErr = document.getElementById('reg-name-err')
  const emailErr = document.getElementById('reg-email-err')

  nameErr.hidden = name !== ''
  if (name === '') {
    document.getElementById('reg-name').focus()
    return
  }
  if (email !== '' && !validateEmail(email)) {
    emailErr.hidden = false
    document.getElementById('field-reg-email').classList.add('has-error')
    document.getElementById('reg-email').focus()
    return
  }

  const deal = {
    id: `d${Date.now()}`,
    property: name,
    price: normalizePrice(document.getElementById('reg-price').value),
    yield: null,
    customer: document.getElementById('reg-customer').value.trim() || '未設定',
    email,
    status: 'active',
    priority: false
  }
  setState({ deals: [...state.deals, deal] })
  clearDraft()
  regOverlay.hidden = true
  showToast({ message: `「${deal.property}」を登録しました` })
  navigate('list')
}

document.getElementById('btn-open-register').addEventListener('click', openRegister)
document.getElementById('btn-close-register').addEventListener('click', closeRegister)
document.getElementById('btn-discard-draft').addEventListener('click', () => {
  clearDraft()
  document.getElementById('reg-name').focus()
})
document.getElementById('btn-do-register').addEventListener('click', doRegister)

/* 入力のたびに自動保存。エラーの解除は修正中リアルタイム(判定はblur時) */
REG_FIELDS.forEach((id) => {
  document.getElementById(id).addEventListener('input', () => {
    scheduleDraftSave()
    if (id === 'reg-email' && validateEmail(document.getElementById(id).value.trim())) {
      document.getElementById('reg-email-err').hidden = true
      document.getElementById('field-reg-email').classList.remove('has-error')
    }
    if (id === 'reg-name' && document.getElementById(id).value.trim() !== '') {
      document.getElementById('reg-name-err').hidden = true
    }
  })
})

document.getElementById('reg-email').addEventListener('blur', (e) => {
  const value = e.target.value.trim()
  const invalid = value !== '' && !validateEmail(value)
  document.getElementById('reg-email-err').hidden = !invalid
  document.getElementById('field-reg-email').classList.toggle('has-error', invalid)
})

document.getElementById('btn-reply-unanswered').addEventListener('click', () => {
  showToast({ message: '未返信11件の返信を開始しました' })
})

/* 送信トリガの規律: Enterでは登録しない(誤送信防止)。
   Enter=次のフィールドへ / ⌘+Enter(mac)・Ctrl+Enter(win)=登録。IME変換確定のEnterは素通し */
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform)

document.getElementById('register-form').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' || e.isComposing) return
  e.preventDefault()
  if ((IS_MAC && e.metaKey) || (!IS_MAC && e.ctrlKey)) {
    doRegister()
    return
  }
  const i = REG_FIELDS.indexOf(e.target.id)
  if (i >= 0 && i < REG_FIELDS.length - 1) {
    document.getElementById(REG_FIELDS[i + 1]).focus()
  } else {
    document.getElementById('btn-do-register').focus()
  }
})

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !regOverlay.hidden) closeRegister()
})

/* 初期化 */
renderList()
loadRecent()
