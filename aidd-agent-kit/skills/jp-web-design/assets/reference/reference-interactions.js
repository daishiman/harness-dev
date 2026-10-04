'use strict'

/* 参照HTML共通の最小操作層。見た目だけの操作部品を残さず、ARIAと表示状態を同時に更新する。 */
;(function initReferenceInteractions(global) {
  const SELECTOR = 'button:not([disabled]), [role="radio"]:not([aria-disabled="true"])'

  function showStatus(target, message) {
    const node = typeof target === 'string' ? document.querySelector(target) : target
    if (!node) return
    node.textContent = message
    node.hidden = false
  }

  function selectExclusive(container, item) {
    const attribute = item.hasAttribute('aria-checked') ? 'aria-checked' : 'aria-pressed'
    container.querySelectorAll(SELECTOR).forEach((control) => {
      control.setAttribute(attribute, String(control === item))
      control.tabIndex = control === item ? 0 : -1
    })
    item.focus()
    container.dispatchEvent(new CustomEvent('reference:selection', { bubbles: true, detail: { item } }))
  }

  function bindExclusive(container) {
    if (container.dataset.referenceBound === 'exclusive') return
    container.dataset.referenceBound = 'exclusive'
    const controls = [...container.querySelectorAll(SELECTOR)]
    const selected = controls.find((item) => item.getAttribute('aria-pressed') === 'true' || item.getAttribute('aria-checked') === 'true') || controls[0]
    controls.forEach((item) => { item.tabIndex = item === selected ? 0 : -1 })
    container.addEventListener('click', (event) => {
      const item = event.target.closest(SELECTOR)
      if (item && container.contains(item)) selectExclusive(container, item)
    })
    container.addEventListener('keydown', (event) => {
      const item = event.target.closest(SELECTOR)
      if (!item || !container.contains(item)) return
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        selectExclusive(container, item)
        return
      }
      const directions = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End']
      if (!directions.includes(event.key)) return
      event.preventDefault()
      const enabled = [...container.querySelectorAll(SELECTOR)]
      const current = enabled.indexOf(item)
      const next = event.key === 'Home' ? 0
        : event.key === 'End' ? enabled.length - 1
          : (current + (event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1) + enabled.length) % enabled.length
      selectExclusive(container, enabled[next])
    })
  }

  function activateTab(tablist, tab) {
    const selector = tab.dataset.tab
    tablist.querySelectorAll('[data-tab]').forEach((item) => {
      const active = item === tab
      if (active) item.setAttribute('aria-current', 'page')
      else item.removeAttribute('aria-current')
      item.tabIndex = active ? 0 : -1
    })
    document.querySelectorAll(`[data-tab-panel][data-tabs-owner="${tablist.id}"]`).forEach((panel) => {
      panel.hidden = panel.dataset.tabPanel !== selector
    })
    tab.focus()
  }

  function bindTabs(tablist) {
    if (tablist.dataset.referenceBound === 'tabs') return
    tablist.dataset.referenceBound = 'tabs'
    const tabs = [...tablist.querySelectorAll('[data-tab]')]
    const active = tabs.find((tab) => tab.hasAttribute('aria-current')) || tabs[0]
    tabs.forEach((tab) => { tab.tabIndex = tab === active ? 0 : -1 })
    tablist.addEventListener('click', (event) => {
      const tab = event.target.closest('[data-tab]')
      if (tab && tablist.contains(tab)) activateTab(tablist, tab)
    })
    tablist.addEventListener('keydown', (event) => {
      const tab = event.target.closest('[data-tab]')
      if (!tab || !['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
      event.preventDefault()
      const current = tabs.indexOf(tab)
      const next = event.key === 'Home' ? 0
        : event.key === 'End' ? tabs.length - 1
          : (current + (event.key === 'ArrowRight' || event.key === 'ArrowDown' ? 1 : -1) + tabs.length) % tabs.length
      activateTab(tablist, tabs[next])
    })
  }

  function validateEmail(input) {
    const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value.trim())
    const error = input.getAttribute('aria-describedby') && document.getElementById(input.getAttribute('aria-describedby'))
    input.setAttribute('aria-invalid', String(!valid))
    input.closest('.field')?.classList.toggle('has-error', !valid)
    if (error) error.hidden = valid
    return valid
  }

  // 用語の表示・固定・閉じる操作は共通の TermUI へ委譲する。
  function bindTerms() { global.TermUI.init() }

  function init(root = document) {
    bindTerms(root)
    root.querySelectorAll('[data-exclusive]').forEach(bindExclusive)
    root.querySelectorAll('[data-tabs]').forEach(bindTabs)
    root.querySelectorAll('[data-disclosure]').forEach((button) => {
      if (button.dataset.referenceBound) return
      button.dataset.referenceBound = 'disclosure'
      button.addEventListener('click', () => {
        const panel = document.getElementById(button.getAttribute('aria-controls'))
        const open = panel?.hidden ?? false
        if (panel) panel.hidden = !open
        button.setAttribute('aria-expanded', String(open))
      })
    })
    root.querySelectorAll('[data-action-message]').forEach((button) => {
      if (button.dataset.referenceBound) return
      button.dataset.referenceBound = 'action'
      button.addEventListener('click', () => {
        if (button.dataset.confirmMessage && !global.confirm(button.dataset.confirmMessage)) return
        showStatus(button.dataset.actionTarget, button.dataset.actionMessage)
      })
    })
    root.querySelectorAll('[data-validate-email]').forEach((input) => {
      if (input.dataset.referenceBound) return
      input.dataset.referenceBound = 'email'
      input.addEventListener('blur', () => validateEmail(input))
      input.addEventListener('input', () => {
        if (input.getAttribute('aria-invalid') === 'true' && validateEmail(input)) validateEmail(input)
      })
    })
    root.querySelectorAll('[data-clear-form]').forEach((button) => {
      if (button.dataset.referenceBound) return
      button.dataset.referenceBound = 'clear'
      button.addEventListener('click', () => {
        const form = document.querySelector(button.dataset.clearForm)
        form?.reset()
        form?.querySelectorAll('input, textarea').forEach((control) => { control.value = '' })
        form?.querySelectorAll('select').forEach((control) => { control.selectedIndex = 0 })
        form?.querySelectorAll('[aria-invalid]').forEach((input) => {
          input.setAttribute('aria-invalid', 'false')
          input.closest('.field')?.classList.remove('has-error')
          const error = input.getAttribute('aria-describedby') && document.getElementById(input.getAttribute('aria-describedby'))
          if (error) error.hidden = true
        })
        showStatus(button.dataset.actionTarget, button.dataset.actionMessage || '入力をクリアしました')
      })
    })
    root.querySelectorAll('[data-filter-table]').forEach((select) => {
      if (select.dataset.referenceBound) return
      select.dataset.referenceBound = 'filter'
      select.addEventListener('change', () => {
        document.querySelectorAll(`${select.dataset.filterTable} tbody tr`).forEach((row) => {
          row.hidden = select.value !== 'all' && row.dataset.status !== select.value
        })
      })
    })
    root.querySelectorAll('[data-sort-table]').forEach((button) => {
      if (button.dataset.referenceBound) return
      button.dataset.referenceBound = 'sort'
      button.addEventListener('click', () => {
        const table = document.querySelector(button.dataset.sortTable)
        const tbody = table?.tBodies[0]
        if (!tbody) return
        const direction = button.dataset.direction === 'ascending' ? 'descending' : 'ascending'
        button.dataset.direction = direction
        button.closest('th')?.setAttribute('aria-sort', direction)
        const factor = direction === 'ascending' ? 1 : -1
        const rows = [...tbody.rows].sort((a, b) => factor * (Number(a.dataset.sortValue) - Number(b.dataset.sortValue)))
        rows.forEach((row) => tbody.appendChild(row))
      })
    })
  }

  global.ReferenceUI = { init, showStatus, selectExclusive, activateTab, validateEmail, bindTerms }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init())
  else init()
})(window)
