/**
 * ux-design 実装パターン集(React + TypeScript)
 * SKILL.md の各節に対応する、ドメイン非依存の hooks / ユーティリティ。
 * vanilla JS の参照実装は Skill jp-web-design の assets/reference/app.js。
 *
 * 依存: react のみ。コピーして使う(npmパッケージ化しない)。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

/* ============================================================
 * §4-1 下書き自動保存 — useDraft
 * 入力欄2つ以上のフォームに標準装備。
 * 復元は黙ってやらない: restored フラグでUIに「復元しました+破棄」を出すこと。
 * ============================================================ */
export interface DraftOptions {
  /** 保存キー。「アプリ名:フォーム名:v1」の形式 */
  key: string
  /** debounce ms(既定600) */
  delay?: number
  /** 下書きのTTL(ms)。既定7日。古い下書きは復元しない */
  ttl?: number
}

export function useDraft<T extends Record<string, unknown>>(
  empty: T,
  { key, delay = 600, ttl = 7 * 24 * 60 * 60 * 1000 }: DraftOptions
) {
  const [values, setValues] = useState<T>(empty)
  const [restored, setRestored] = useState(false)
  const [savedAt, setSavedAt] = useState<Date | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>()

  // 初回マウント時に復元(TTL切れは破棄)
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(key)
      if (!raw) return
      const { data, at } = JSON.parse(raw) as { data: T; at: number }
      if (Date.now() - at > ttl) {
        window.localStorage.removeItem(key)
        return
      }
      const hasContent = Object.values(data).some((v) => String(v ?? '').trim() !== '')
      if (hasContent) {
        setValues(data)
        setRestored(true) // UI側で「入力途中の下書きを復元しました」+破棄ボタンを表示
      }
    } catch {
      window.localStorage.removeItem(key)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const update = useCallback(
    (patch: Partial<T>) => {
      setValues((prev) => {
        const next = { ...prev, ...patch }
        clearTimeout(timer.current)
        timer.current = setTimeout(() => {
          const hasContent = Object.values(next).some((v) => String(v ?? '').trim() !== '')
          if (hasContent) {
            window.localStorage.setItem(key, JSON.stringify({ data: next, at: Date.now() }))
            setSavedAt(new Date()) // UIに「下書きを自動保存しました(HH:MM)」
          } else {
            window.localStorage.removeItem(key)
            setSavedAt(null)
          }
        }, delay)
        return next
      })
    },
    [key, delay]
  )

  /** 破棄(明示操作)/ 送信成功時にも必ず呼ぶ */
  const clear = useCallback(() => {
    clearTimeout(timer.current)
    window.localStorage.removeItem(key)
    setValues(empty)
    setRestored(false)
    setSavedAt(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return { values, update, clear, restored, savedAt }
}

/* ============================================================
 * §5-1 一括選択 — useBulkSelection
 * 全選択は「表示中(絞り込み後)」を対象にする。選択バーとセットで使う。
 * ============================================================ */
export function useBulkSelection<T>(
  visibleItems: T[],
  getId: (item: T) => string,
  /** 選択可能条件(未達は全選択からも自動除外し、理由を行内に表示すること) */
  selectable: (item: T) => boolean = () => true
) {
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set())

  const selectableIds = useMemo(
    () => visibleItems.filter(selectable).map(getId),
    [visibleItems, selectable, getId]
  )

  const toggle = useCallback((id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }, [])

  /** ヘッダーの全選択チェックボックス(表示中のみ対象) */
  const toggleAllVisible = useCallback(() => {
    setSelected((prev) =>
      selectableIds.every((id) => prev.has(id)) ? new Set() : new Set(selectableIds)
    )
  }, [selectableIds])

  /** Shift+クリックの範囲選択: 直前のクリック行から今回の行まで */
  const lastIndex = useRef<number>(-1)
  const clickRow = useCallback(
    (index: number, shiftKey: boolean) => {
      if (shiftKey && lastIndex.current >= 0) {
        const [a, b] = [lastIndex.current, index].sort((x, y) => x - y)
        const range = visibleItems.slice(a, b + 1).filter(selectable).map(getId)
        setSelected((prev) => new Set([...prev, ...range]))
      } else {
        toggle(getId(visibleItems[index]))
      }
      lastIndex.current = index
    },
    [visibleItems, selectable, getId, toggle]
  )

  return {
    selected,
    count: selected.size,
    isSelected: (id: string) => selected.has(id),
    allVisibleSelected: selectableIds.length > 0 && selectableIds.every((id) => selected.has(id)),
    toggle,
    toggleAllVisible,
    clickRow,
    clearSelection: () => setSelected(new Set()),
  }
}

/* ============================================================
 * §4-2 送信トリガ — useSubmitKeys
 * Enter=次のフィールドへ / ⌘+Enter(mac)・Ctrl+Enter(win)=送信 / IME中は素通し。
 * modLabel をキーキャップUI(<kbd>)でボタン近傍に必ず表示する。
 * ============================================================ */
export function useSubmitKeys(fieldIds: string[], onSubmit: () => void) {
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== 'Enter' || e.nativeEvent.isComposing) return // IMEガード
      e.preventDefault()
      if ((isMac && e.metaKey) || (!isMac && e.ctrlKey)) {
        onSubmit()
        return
      }
      const i = fieldIds.indexOf((e.target as HTMLElement).id)
      const nextId = i >= 0 && i < fieldIds.length - 1 ? fieldIds[i + 1] : null
      if (nextId) document.getElementById(nextId)?.focus()
    },
    [fieldIds, onSubmit, isMac]
  )

  return { onKeyDown, modLabel: isMac ? '⌘' : 'Ctrl' }
}

/* ============================================================
 * §4-2 バリデーションのタイミング — useLateValidation
 * 「blurで判定・修正中はリアルタイムで解除」(reward early, punish late)
 * ============================================================ */
export function useLateValidation(validate: (value: string) => string | null) {
  const [error, setError] = useState<string | null>(null)
  return {
    error,
    /** input の onBlur に */
    onBlur: (e: React.FocusEvent<HTMLInputElement>) => setError(validate(e.target.value)),
    /** input の onChange 内で呼ぶ(直った瞬間に消す。新たに赤くはしない) */
    onChange: (value: string) => {
      if (error && validate(value) === null) setError(null)
    },
  }
}

/* ============================================================
 * §5-2 並行処理 — runWithConcurrency
 * 直列で待たせない(同時3〜5本)。進捗は per-item コールバックで
 * 「全体バー+項目別ステータス」の2階建てを作る。
 * ============================================================ */
export type ItemState = 'pending' | 'running' | 'done' | 'failed'

export async function runWithConcurrency<T, R>(
  items: T[],
  worker: (item: T, index: number) => Promise<R>,
  {
    concurrency = 4,
    onItem,
  }: {
    concurrency?: number
    /** 項目ごとの状態変化(UIの行ステータス・全体カウンタ更新に使う) */
    onItem?: (index: number, state: ItemState, result?: R, error?: unknown) => void
  } = {}
): Promise<Array<{ item: T; ok: boolean; result?: R; error?: unknown }>> {
  const results: Array<{ item: T; ok: boolean; result?: R; error?: unknown }> = new Array(items.length)
  let cursor = 0

  async function lane() {
    while (cursor < items.length) {
      const i = cursor++
      onItem?.(i, 'running')
      try {
        const result = await worker(items[i], i)
        results[i] = { item: items[i], ok: true, result }
        onItem?.(i, 'done', result)
      } catch (error) {
        // 部分成功: 1件の失敗で全体を止めない
        results[i] = { item: items[i], ok: false, error }
        onItem?.(i, 'failed', undefined, error)
      }
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, lane))
  return results
}

/** §5 部分成功: 成功は先へ、失敗は要確認キューへ */
export function splitResults<T, R>(results: Array<{ item: T; ok: boolean; result?: R; error?: unknown }>) {
  return {
    succeeded: results.filter((r) => r.ok),
    /** 要確認キューに隔離し、再試行・修正・スキップの回復経路を必ず付ける(§7) */
    needsReview: results.filter((r) => !r.ok),
  }
}

/* ============================================================
 * §5-3 省略とチェックの両立 — applyWithUndo
 * 「自動でやる・何をしたか見せる・戻せる」の3点セット。
 * 呼び出し側は summary をトースト表示し、Undoボタンに undo を配線する。
 * ============================================================ */
export function applyWithUndo<S>(
  current: S,
  apply: (state: S) => S,
  describe: (before: S, after: S) => string
): { next: S; summary: string; undo: () => S } {
  const next = apply(current)
  return {
    next,
    summary: describe(current, next), // 例: 「13件を自動入力しました(要確認)」
    undo: () => current, // イミュータブルなので前の状態を返すだけで戻る
  }
}

/* ============================================================
 * §4 入力の正規化 — ポステルの法則(入力に寛容・出力は厳格)
 * ============================================================ */

/** 全角数字・全角/半角カンマ・空白入りの文字列を数値に。不正は null(勝手に推測しない) */
export function normalizeNumeric(raw: string): number | null {
  const half = raw.replace(/[０-９]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
  const digits = half.replace(/[,，、\s　]/g, '')
  if (digits === '') return null
  const n = Number(digits)
  return Number.isFinite(n) && n >= 0 ? n : null
}

/** メール形式(要件が緩い一次チェック用。最終判定はサーバー側でも行う) */
export function isEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

/* ============================================================
 * 数値表示 — jp-web-design references/typography-numerals.md の文法(値=変数の描き分け)
 * カンマは .num-sep で縮小、単位は .unit。dangerouslySetInnerHTML を避けた配列版。
 * ============================================================ */
const NUM_FORMAT = new Intl.NumberFormat('ja-JP')

/** 例: <span className="num-display">{formatNumParts(23048)}</span><span className="unit">万円</span> */
export function formatNumParts(value: number | null): Array<string | JSX.Element> {
  if (value == null) return ['—']
  return NUM_FORMAT.format(value)
    .split(',')
    .flatMap((chunk, i) =>
      i === 0 ? [chunk] : [<span key={i} className="num-sep">,</span>, chunk]
    )
}
