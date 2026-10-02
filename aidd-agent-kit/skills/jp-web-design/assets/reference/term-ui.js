/* 用語の段階開示。説明はリンク先の dt/dd だけが持つ。
   カタログとレポートで同じ表示・固定・閉じる操作を使い、図の値の tooltip とは箱を分ける。 */
(function (global) {
  'use strict'
  if (global.TermUI) return
  let bound = false
  let pop, pinned, hovered, focused, describedTerm
  let restoringFocus = false
  const termOf = (event) => event.target.closest?.('a.term[href^="#"]')

  function clearDescription() {
    if (!describedTerm) return
    const ids = (describedTerm.getAttribute('aria-describedby') || '').split(/\s+/).filter((id) => id && id !== pop.id)
    if (ids.length) describedTerm.setAttribute('aria-describedby', ids.join(' '))
    else describedTerm.removeAttribute('aria-describedby')
    describedTerm = null
  }

  function hide() {
    if (pop) pop.hidden = true
    clearDescription()
    pinned = hovered = focused = null
  }

  function show(term) {
    let dt
    try { dt = document.getElementById(decodeURIComponent(term.getAttribute('href').slice(1))) }
    catch { return false }
    const dd = dt?.nextElementSibling
    if (dd?.tagName !== 'DD') return false
    if (!pop) {
      pop = document.createElement('div')
      pop.id = 'term-pop'
      pop.className = 'tooltip tip-rich'
      pop.setAttribute('role', 'tooltip')
      pop.hidden = true
      document.body.appendChild(pop)
    }
    clearDescription()
    pop.textContent = ''
    const label = document.createElement('b')
    label.textContent = term.dataset.term || dt.textContent
    pop.append(label, ...[...dd.children].map((line) => {
      const row = document.createElement('span')
      row.textContent = line.textContent
      return row
    }))
    pop.hidden = false
    describedTerm = term
    const ids = (term.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean)
    term.setAttribute('aria-describedby', [...new Set([...ids, pop.id])].join(' '))
    const box = term.getBoundingClientRect()
    const left = Math.max(8, Math.min(box.left, global.innerWidth - pop.offsetWidth - 8))
    const below = box.bottom + 8
    const top = below + pop.offsetHeight > global.innerHeight - 8 ? Math.max(8, box.top - pop.offsetHeight - 8) : below
    pop.style.left = `${left}px`
    pop.style.top = `${top}px`
    return true
  }

  function init() {
    if (bound) return
    bound = true
    // 文書に一度だけ委譲するので、再 init や後から追加した用語で状態機械を増やさない。
    document.addEventListener('mouseover', (event) => {
      if (pinned) return
      const term = termOf(event)
      if (term) { if (show(term)) hovered = term }
      else {
        hovered = null
        if (focused) show(focused)
        else if (describedTerm) hide()
      }
    })
    document.addEventListener('focusin', (event) => {
      const term = termOf(event)
      if (!restoringFocus && !pinned && term && show(term)) focused = term
    })
    document.addEventListener('focusout', (event) => {
      if (termOf(event) !== focused) return
      focused = null
      if (!pinned) {
        if (hovered) show(hovered)
        else hide()
      }
    })
    document.addEventListener('click', (event) => {
      const term = termOf(event)
      if (!term) { if (pinned) hide(); return }
      const same = pinned === term
      hide()
      if (same) event.preventDefault()
      else if (show(term)) { event.preventDefault(); pinned = term }
      // 説明が見つからない場合はリンク本来の遷移を残す。
    })
    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || (!pinned && !hovered && !focused)) return
      const term = pinned
      hide()
      if (!term) return
      restoringFocus = true
      term.focus({ preventScroll: true })
      restoringFocus = false
    })
    global.addEventListener('scroll', hide, { passive: true })
    global.addEventListener('resize', hide, { passive: true })
  }

  global.TermUI = { init }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init)
  else init()
})(window);
