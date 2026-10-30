"use strict";
// ヒアリング（一括回答と様式提案）。質問の正本は references/intake-questions.json。
// - template: 全質問を 1 枚の一括回答シートにする（分かっている値は「確認のみ」、前回までの傾向は参考・要確認）。
// - apply: 一括回答を検査し、正しい値だけを brief.json へ、全回答と出典を <project>/intake.json へ書く。
// - residual: 不足・矛盾・確定事実の読み返し・様式提案の要否だけを返す。
// - assertResolved: 必須の項目に未解決や仮置きが残っていれば止める（essence-baseline と finalize の前）。
// 依存は Node 標準と ajv だけ。回答には個人情報が入るため、記録は案件フォルダにだけ置く（E3）。
const fs = require("node:fs");
const path = require("node:path");
const Ajv = require("ajv");

const ROOT = path.resolve(__dirname, "..");
const FILES = {
  questions: path.join(ROOT, "references", "intake-questions.json"),
  essence: path.join(ROOT, "references", "essence.json"),
  contract: path.join(ROOT, "references", "design-contract.json"),
  presets: path.join(ROOT, "references", "presets"),
  brief: path.join(ROOT, "schemas", "brief.schema.json"),
  intake: path.join(ROOT, "schemas", "intake.schema.json"),
  proposals: path.join(ROOT, "schemas", "style-proposals.schema.json"),
};
const STYLE_PATH = "/stylePreferences";
const PROPOSALS_FILE = "style-proposals.json";
const SOURCES = ["answer", "document", "preset-reconfirmed", "placeholder", "proposal"];
const SOURCE_LABEL = {
  answer: "今回の回答",
  document: "今回の資料",
  "preset-reconfirmed": "前回の値を今回の値として再確認",
  placeholder: "仮置き",
  proposal: "様式提案から選択",
};
const TYPES = new Set(["text", "list", "choice", "multi", "boolean", "date", "integer", "url", "page-size"]);
const OVERRIDABLE = new Set(["briefPath", "example", "prompt", "label", "options"]);
const PLACEHOLDER =
  /未定|未確認|要確認|調整中|仮置き|[（(]仮[）)]|^仮$|あとで|後で決め|TBD|TBA|xxx|〇〇|○○|××|\?\?|？？|前回と同じ|前回どおり|前回通り|いつもと同じ|^同じ$|dummy|sample|placeholder|lorem/i;
const PLACEHOLDER_HOST = /^(example\.(com|net|org)|localhost|127\.0\.0\.1)$|\.(test|invalid|example|localhost)$/i;
const OMAKASE = /^(お?まかせ|お?任せ)(します|する|る|ます|で|でお願いします)?$|^omakase$/i;
const SKIP = /^(なし|無し|ナシ|該当なし|該当無し|特になし|特に無し|ありません|特にありません|不要|いない|いません)$/;
// 様式として具体的でない言葉（雰囲気語）。これだけの回答は様式提案の根拠に回す（様式が決まるまで提案する）。
const VAGUE =
  /^(とにかく|なんか|何か)?(おしゃれ|オシャレ|お洒落|かっこ(いい|よく)|カッコ(いい|イイ|よく)|格好(いい|良い|よく|良く)|かわいい|可愛い|カワイイ|きれい|綺麗|キレイ|いい感じ|良い感じ|イイ感じ|素敵|すてき|ステキ|いい雰囲気|雰囲気(重視)?|イメージ(重視)?|なんでも|何でも|どれでも|お好みで|目立つ|映える)(な|に|く|感じ|もの|の|で)?$/;
const PHOTO_STYLE = /写真|実写|フォト/;
const PAGES = { A3: [297, 420], A4: [210, 297], A5: [148, 210], B4: [257, 364], B5: [182, 257] };
const WEEK = "日月火水木金土";

const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const clone = (v) => (v === undefined ? undefined : JSON.parse(JSON.stringify(v)));
const canon = (v) =>
  Array.isArray(v)
    ? v.map(canon)
    : isObj(v)
      ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canon(v[k])]))
      : v;
const same = (a, b) => JSON.stringify(canon(a ?? null)) === JSON.stringify(canon(b ?? null));
const readJSON = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const readOptional = (p) => (fs.existsSync(p) ? readJSON(p) : undefined);
const writeJSON = (p, o) => {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(o, null, 2) + "\n");
};
const strings = (v) =>
  Array.isArray(v)
    ? v.flatMap(strings)
    : isObj(v)
      ? Object.values(v).flatMap(strings)
      : typeof v === "string"
        ? [v]
        : [];
const meaningful = (v) =>
  v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && !v.length) && !(isObj(v) && !Object.keys(v).length);

// brief 内の場所（JSON pointer）。キーは英数字・_・- だけなのでエスケープは要らない。
const segs = (ptr) => ptr.split("/").slice(1);
function getPointer(o, ptr) {
  let v = o;
  for (const s of segs(ptr)) {
    if (!isObj(v) || !(s in v)) return undefined;
    v = v[s];
  }
  return v;
}
function setPointer(o, ptr, val) {
  const ks = segs(ptr);
  let v = o;
  for (const s of ks.slice(0, -1)) {
    if (!isObj(v[s])) v[s] = {};
    v = v[s];
  }
  v[ks.at(-1)] = val;
}
function deletePointer(o, ptr) {
  const ks = segs(ptr);
  let v = o;
  for (const s of ks.slice(0, -1)) {
    if (!isObj(v[s])) return;
    v = v[s];
  }
  delete v[ks.at(-1)];
}

// 回答・回答シートを plugin の中へ書かせない（E3）。
function outsidePlugin(p, what) {
  const target = path.resolve(p);
  let probe = target;
  while (!fs.existsSync(probe) && path.dirname(probe) !== probe) probe = path.dirname(probe);
  const real = path.join(fs.realpathSync(probe), path.relative(probe, target));
  const root = fs.realpathSync(ROOT);
  if (real === root || real.startsWith(root + path.sep))
    throw Error(`${what}は plugin の外（案件フォルダ）に置いてください。回答には個人情報が含まれるためです（E3）: ${p}`);
  return target;
}
function input(x, what) {
  if (x === undefined || x === null) return undefined;
  if (typeof x === "string") return readJSON(path.resolve(x));
  if (isObj(x) || Array.isArray(x)) return x;
  throw Error(`${what} は JSON のオブジェクトか JSON ファイルのパスで渡してください`);
}

const ajv = new Ajv({ allErrors: true, strict: false });
const compiled = new Map();
function validator(file) {
  if (!compiled.has(file)) compiled.set(file, ajv.compile(readJSON(file)));
  return compiled.get(file);
}
let briefSchema;
function briefSub(ptr) {
  let s = (briefSchema ??= readJSON(FILES.brief));
  for (const k of segs(ptr)) {
    if (isObj(s?.properties?.[k])) s = s.properties[k];
    else if (isObj(s?.additionalProperties)) s = s.additionalProperties;
    else return null;
  }
  return s;
}
function briefError(ptr, value) {
  const id = "brief:" + ptr;
  if (!compiled.has(id)) {
    const sub = briefSub(ptr);
    compiled.set(id, sub ? ajv.compile(sub) : null);
  }
  const v = compiled.get(id);
  return !v || v(value) ? null : ajv.errorsText(v.errors, { dataVar: ptr });
}

// preset は id か別名（preset.json の aliases）で選ぶ。init と同じく briefExample の上に preset.brief を重ねた値が「前回の値」。
// brief に場所を持たない質問（ロゴなど）の前回の値は preset.json の intakePrefill（{質問 id かキー: 値}）に置く。
// どちらも案件固有の値なので plugin 共通の質問には書かない（案件固有の値を汎用の質問へ混ぜない）。テンプレートでは「前回の値・要確認」として見せるだけで、回答の雛形には入れない。
function presetInfo(name) {
  if (name === undefined || name === null || name === "") return null;
  const ids = fs.existsSync(FILES.presets)
    ? fs.readdirSync(FILES.presets).filter((id) => fs.statSync(path.join(FILES.presets, id)).isDirectory())
    : [];
  for (const dirName of ids) {
    const dir = path.join(FILES.presets, dirName);
    const doc = readOptional(path.join(dir, "preset.json")) ?? {};
    if (dirName !== name && doc.id !== name && !(doc.aliases || []).includes(name)) continue;
    const example = typeof doc.briefExample === "string" ? readOptional(path.join(ROOT, doc.briefExample)) : undefined;
    return {
      id: doc.id ?? dirName,
      previous: { ...(isObj(example) ? example : {}), ...(isObj(doc.brief) ? clone(doc.brief) : {}) },
      extra: readOptional(path.join(dir, "intake-questions.json")),
      prefill: isObj(doc.intakePrefill) ? doc.intakePrefill : {},
    };
  }
  throw Error("未知の preset です: " + name);
}

const isFact = (q) => q.mustFact === true && typeof q.briefPath === "string";
const isReadback = (q) => q.askWhen?.readback === true;

// 質問の一覧を読み、preset の追加・差し替えを重ね、形を検査する。
function questions(presetName = null) {
  const doc = readJSON(FILES.questions);
  const preset = presetInfo(presetName);
  const list = clone(doc.questions);
  if (preset?.extra !== undefined) {
    if (!isObj(preset.extra)) throw Error(`preset ${preset.id} の intake-questions.json は {questions, overrides} の形にしてください`);
    for (const [id, o] of Object.entries(preset.extra.overrides ?? {})) {
      const q = list.find((x) => x.id === id);
      if (!q) throw Error(`preset ${preset.id} の差し替え先の質問がありません: ${id}`);
      for (const [k, v] of Object.entries(o)) {
        if (!OVERRIDABLE.has(k)) throw Error(`preset で変えられない項目です: ${id}.${k}`);
        q[k] = clone(v);
      }
    }
    list.push(...clone(preset.extra.questions ?? []));
  }
  const groups = doc.groups.map((g) => g.id);
  const clauses = new Set(readJSON(FILES.essence).clauses.map((c) => c.id));
  const byId = {},
    byKey = {};
  const bad = (q, msg) => {
    throw Error(`intake-questions の質問 ${q?.id ?? "?"}: ${msg}`);
  };
  for (const q of list) {
    if (!isObj(q) || typeof q.id !== "string" || !/^[a-z][a-z0-9-]*$/.test(q.id)) bad(q, "id は英小文字・数字・ハイフンにする");
    if (byId[q.id]) bad(q, "id が重複しています");
    if (!groups.includes(q.group)) bad(q, "未知の group: " + q.group);
    if (!Array.isArray(q.essence) || !q.essence.length || q.essence.some((e) => !clauses.has(e)))
      bad(q, "essence に essence.json の条項 ID を 1 つ以上書く（R3）");
    if (!TYPES.has(q.answerType)) bad(q, "未知の answerType: " + q.answerType);
    if (["choice", "multi"].includes(q.answerType) && !(Array.isArray(q.options) && q.options.length)) bad(q, "options が必要");
    if (q.briefPath !== null && !(typeof q.briefPath === "string" && /^(\/[A-Za-z0-9_-]+)+$/.test(q.briefPath) && briefSub(q.briefPath)))
      bad(q, "briefPath が brief.schema.json にありません: " + q.briefPath);
    if (typeof q.prompt !== "string" || !q.prompt.trim()) bad(q, "prompt が必要");
    if (q.mustFact && !q.required) bad(q, "mustFact の質問は required にする");
    q.key = q.briefPath ?? "intake." + q.id;
    if (byKey[q.key]) bad(q, "保存キーが重複しています: " + q.key);
    byId[q.id] = q;
    byKey[q.key] = q;
  }
  for (const q of list) {
    const w = q.askWhen;
    if (w !== undefined && !isReadback(q) && !(isObj(w) && byKey[w.key] && ["equals", "includes", "anyMatch", "anyNotMatch"].some((k) => k in w)))
      bad(q, "askWhen の形か参照先が不正です");
    if (q.partOf !== undefined && !byId[q.partOf]) bad(q, "partOf の参照先がありません: " + q.partOf);
  }
  const previousAnswers = {};
  for (const [k, v] of Object.entries(preset?.prefill ?? {})) {
    const q = byKey[k] ?? byId[k];
    if (!q || q.briefPath) throw Error(`preset ${preset.id} の intakePrefill に使えないキーです（brief に場所を持たない質問だけ）: ${k}`);
    previousAnswers[q.key] = isObj(v) && "value" in v ? v.value : v;
  }
  // init が brief に入れる値（initDefaults と preset）。テンプレートで「初期値」「前回の値」として見せる。
  const neutral = readOptional(FILES.contract)?.initDefaults;
  const base = isObj(neutral)
    ? { count: neutral.variantCount, whiteCount: neutral.whiteCount, page: neutral.page, policy: neutral.policy }
    : {};
  return {
    questions: doc.groups.flatMap((g) => list.filter((q) => q.group === g.id)),
    groups: doc.groups,
    byId,
    byKey,
    preset,
    previous: preset?.previous ?? {},
    previousAnswers,
    initial: { ...clone(base), ...clone(preset?.previous ?? {}) },
  };
}
const previousOf = (Q, q) => (q.briefPath ? getPointer(Q.previous, q.briefPath) : Q.previousAnswers[q.key]);
function keyFor(Q, k) {
  if (typeof k !== "string") return null;
  if (Q.byKey[k]) return k;
  if (Q.byId[k]) return Q.byId[k].key;
  if (k.startsWith("intake.") && Q.byId[k.slice(7)]) return Q.byId[k.slice(7)].key;
  return null;
}

const pick = (q, x) => {
  const s = typeof x === "string" ? x.trim() : x;
  return q.options.find((o) => o.value === s || o.label === s);
};
const asText = (x) => (typeof x === "number" ? String(x) : x);
const TYPE_RULES = {
  text(q, raw) {
    raw = asText(raw);
    return typeof raw === "string" ? { value: raw.trim() } : { reason: "文章で答えてください" };
  },
  list(q, raw) {
    const items = (Array.isArray(raw) ? raw : [raw]).map(asText);
    if (items.some((x) => typeof x !== "string")) return { reason: "文章か、文章の並びで答えてください" };
    return { value: items.flatMap((x) => x.split(/\r?\n/)).map((x) => x.trim()).filter(Boolean) };
  },
  choice(q, raw) {
    const o = pick(q, raw);
    return o ? { value: o.value } : { reason: "次から選んでください: " + q.options.map((x) => x.label).join(" / ") };
  },
  multi(q, raw) {
    const items = (Array.isArray(raw) ? raw : [raw])
      .flatMap((x) => (typeof x === "string" ? x.split(/[、,，\n]/) : [x]))
      .map((x) => (typeof x === "string" ? x.trim() : x))
      .filter((x) => x !== "");
    const picked = items.map((x) => pick(q, x));
    if (!items.length || picked.some((o) => !o))
      return { reason: "次から選んでください（複数可）: " + q.options.map((x) => x.label).join(" / ") };
    return { value: [...new Set(picked.map((o) => o.value))] };
  },
  boolean(q, raw) {
    if (typeof raw === "boolean") return { value: raw };
    const s = String(raw).trim().toLowerCase();
    if (/^(はい|yes|y|true|ok|正しい|間違いない|間違いありません)$/.test(s)) return { value: true };
    if (/^(いいえ|no|n|false|違う|違います)$/.test(s)) return { value: false };
    return { reason: "「はい」か「いいえ」で答えてください" };
  },
  integer(q, raw) {
    const n = typeof raw === "number" ? raw : typeof raw === "string" && /^\s*\d+\s*$/.test(raw) ? Number(raw) : NaN;
    if (!Number.isInteger(n)) return { reason: "整数で答えてください" };
    if ((q.min !== undefined && n < q.min) || (q.max !== undefined && n > q.max))
      return { reason: `${q.min ?? ""}〜${q.max ?? ""} で答えてください` };
    return { value: n };
  },
  date(q, raw) {
    if (typeof raw !== "string") return { reason: "年・月・日を文章で書いてください" };
    const found = [...raw.matchAll(/(\d{4})\s*[年/.-]\s*(\d{1,2})\s*[月/.-]\s*(\d{1,2})\s*日?/g)];
    if (!found.length)
      return {
        reason: /\d{1,2}\s*月\s*\d{1,2}\s*日/.test(raw)
          ? "年が抜けています。年から書いてください"
          : "年・月・日の形で書いてください（例 2026年12月6日（日））",
      };
    for (const m of found) {
      const [y, mo, d] = m.slice(1, 4).map(Number);
      const dt = new Date(Date.UTC(y, mo - 1, d));
      if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d)
        return { reason: "存在しない日付です: " + m[0] };
      const w = raw
        .slice(m.index + m[0].length)
        .match(/^\s*(?:[（(]\s*([日月火水木金土])(?:曜日?)?\s*[）)]|([日月火水木金土])曜)/);
      const given = w && (w[1] ?? w[2]);
      if (given && given !== WEEK[dt.getUTCDay()])
        return { reason: `曜日が暦と合いません（${y}年${mo}月${d}日は${WEEK[dt.getUTCDay()]}曜日）` };
    }
    return { value: raw.trim() };
  },
  url(q, raw) {
    if (typeof raw !== "string" || !/^https?:\/\//i.test(raw.trim())) return { reason: "http:// か https:// で始まる URL を書いてください" };
    let u;
    try {
      u = new URL(raw.trim());
    } catch {
      return { reason: "URL の形になっていません" };
    }
    if (PLACEHOLDER_HOST.test(u.hostname))
      return { state: "placeholder", reason: `例示用のアドレス（${u.hostname}）です。今回の申込先を書いてください` };
    return { value: raw.trim() };
  },
  "page-size"(q, raw) {
    const hint = "A3・A4・A5・B4・B5 と縦か横、または 幅×高さ（mm）で書いてください";
    if (isObj(raw) && Number(raw.width) > 0 && Number(raw.height) > 0)
      return { value: { width: Number(raw.width), height: Number(raw.height) } };
    if (typeof raw !== "string") return { reason: hint };
    const s = raw.normalize("NFKC").trim();
    const named = s.match(/^([AB]\d)\s*(?:判|サイズ)?\s*[、,]?\s*(縦|横|portrait|landscape)?(?:向き)?$/i);
    if (named) {
      const size = PAGES[named[1].toUpperCase()];
      if (!size) return { reason: hint };
      if (!named[2]) return { reason: "縦か横かも書いてください" };
      const land = /横|landscape/i.test(named[2]);
      return { value: { width: land ? size[1] : size[0], height: land ? size[0] : size[1] } };
    }
    const mm = s.match(/^(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×*]\s*(\d+(?:\.\d+)?)\s*(?:mm)?$/i);
    return mm ? { value: { width: Number(mm[1]), height: Number(mm[2]) } } : { reason: hint };
  },
};

// 1 つの回答を状態にする: ok / omakase / skip / placeholder / invalid / empty。
function normalize(Q, q, raw, brief) {
  if (!meaningful(raw) || (typeof raw === "string" && !raw.trim()) || (Array.isArray(raw) && !strings(raw).some((s) => s.trim()) && !raw.some((x) => typeof x !== "string")))
    return { state: "empty" };
  const single = typeof raw === "string" ? raw.trim() : Array.isArray(raw) && raw.length === 1 && typeof raw[0] === "string" ? raw[0].trim() : null;
  if (single !== null && OMAKASE.test(single)) return { state: "omakase", value: single };
  if (single !== null && q.allowSkip && SKIP.test(single)) return { state: "skip" };
  const ph = strings(raw).find((s) => PLACEHOLDER.test(s.trim()));
  if (ph !== undefined) {
    const prev = previousOf(Q, q);
    const again = /前回|いつも|^同じ$/.test(ph.trim());
    return {
      state: "placeholder",
      value: raw,
      reason: again
        ? "「前回と同じ」は、今回の具体的な値に書き直してください" + (meaningful(prev) ? `（前回の値: ${show(q, prev)}）` : "")
        : `仮置き（${ph.trim()}）のままです。今回の値を書いてください`,
    };
  }
  const r = TYPE_RULES[q.answerType](q, raw);
  if (r.reason) return { state: r.state ?? "invalid", value: raw, reason: r.reason };
  if (q.briefPath) {
    const err = briefError(q.briefPath, q.answerType === "page-size" ? { ...(brief?.page ?? {}), ...r.value } : r.value);
    if (err) return { state: "invalid", value: raw, reason: "brief の型に合いません: " + err };
  }
  return { state: "ok", value: r.value };
}

function show(q, v) {
  if (v === null || v === undefined) return "";
  if (q?.answerType === "page-size" && isObj(v)) return `${v.width}×${v.height}mm`;
  const label = (x) => q?.options?.find((o) => o.value === x)?.label ?? x;
  if (Array.isArray(v)) return v.map(label).join("・");
  if (typeof v === "boolean") return v ? "はい" : "いいえ";
  return String(label(v));
}

// 選ばれた様式提案と回答の一致を確かめる。食い違いは理由の文、一致は null。
function proposalMismatch(dir, labels) {
  const doc = dir ? readOptional(path.join(dir, PROPOSALS_FILE)) : undefined;
  if (!doc) return `様式提案（${PROPOSALS_FILE}）がありません。提案を書いてから選んでください`;
  const v = validator(FILES.proposals);
  if (!v(doc)) return `${PROPOSALS_FILE} が schema に合いません: ` + ajv.errorsText(v.errors);
  const ids = doc.proposals.map((p) => p.id),
    names = doc.proposals.map((p) => p.label);
  if (new Set(ids).size !== ids.length || new Set(names).size !== names.length) return "提案の id か label が重複しています";
  if (!doc.chosen.length) return "提案がまだ選ばれていません（chosen が空）";
  const unknown = doc.chosen.filter((id) => !ids.includes(id));
  if (unknown.length) return "chosen に存在しない提案 id があります: " + unknown.join(", ");
  const chosen = doc.chosen.map((id) => names[ids.indexOf(id)]);
  if (!same([...new Set(labels)].sort(), [...new Set(chosen)].sort()))
    return `選ばれた提案（${chosen.join("・")}）と様式の回答（${labels.join("・")}）が一致しません`;
  return null;
}

// 全質問の状態・適用の有無・未解決・矛盾・読み返しの要否・様式提案の要否を計算する。
function evaluate(Q, rec, brief, dir) {
  const st = {};
  const skipped = new Set((rec.skipped || []).map((s) => s.path));
  for (const q of Q.questions) {
    const a = rec.answers?.[q.key];
    if (!a) {
      st[q.key] = { state: skipped.has(q.key) ? "skip" : "empty" };
      continue;
    }
    let n = normalize(Q, q, a.value, brief);
    if (a.source === "placeholder" && n.state !== "empty" && n.state !== "placeholder")
      n = { state: "placeholder", value: a.value, reason: "仮置きとして記録されています。今回の値を書いてください" };
    if (q.key === STYLE_PATH && a.source === "proposal" && n.state === "ok") {
      const why = proposalMismatch(dir, n.value);
      if (why) n = { state: "mismatch", value: a.value, reason: why };
    }
    st[q.key] = { ...n, source: a.source };
  }
  const readback = Q.questions.filter(isFact).every((q) => ["ok", "skip"].includes(st[q.key].state));
  const known = (key) => {
    const s = st[key];
    // 様式は今回の回答だけで判定する。雰囲気語だけの回答や提案との食い違いは、決まるまで条件の判定に使わない。
    if (key === STYLE_PATH && s?.state !== "skip")
      return s?.state === "ok" && (s.source === "proposal" || !s.value.every((t) => VAGUE.test(t.trim()))) ? { known: true, value: s.value } : { known: false };
    if (s?.state === "ok") return { known: true, value: s.value };
    if (s?.state === "skip") return { known: true, value: null };
    const inBrief = key.startsWith("/") ? getPointer(brief, key) : undefined;
    return meaningful(inBrief) ? { known: true, value: inBrief } : { known: false };
  };
  const memo = {};
  const applies = (q) => {
    if (q.key in memo) return memo[q.key];
    const w = q.askWhen;
    let r = true;
    if (w && isReadback(q)) r = readback;
    else if (w) {
      const parent = applies(Q.byKey[w.key]);
      const k = known(w.key);
      if (parent === false) r = false;
      else if (!k.known) r = null;
      else if ("equals" in w) r = k.value === w.equals;
      else if ("includes" in w) r = Array.isArray(k.value) && k.value.includes(w.includes);
      else {
        const re = new RegExp(w.anyMatch ?? w.anyNotMatch);
        const texts = strings(k.value);
        r = "anyMatch" in w ? texts.some((t) => re.test(t)) : texts.some((t) => !re.test(t));
      }
    }
    return (memo[q.key] = r);
  };
  const items = new Map();
  const add = (key, kind, reason) => {
    const old = items.get(key);
    items.set(key, old ? { kind: kind === "conflict" ? kind : old.kind, reason: old.reason + "／" + reason } : { kind, reason });
  };
  for (const q of Q.questions) {
    const s = st[q.key];
    s.applies = applies(q);
    if (s.applies !== true) continue;
    if (isReadback(q)) {
      if (!(s.state === "ok" && s.value === true))
        add(q.key, "readback", s.state === "ok" ? "直す事実があります。直した値を答えてください" : "確定事実の一覧を確かめてください");
      continue;
    }
    const kind = q.askWhen ? "conditional" : "unresolved";
    if (s.state === "invalid" || s.state === "mismatch") add(q.key, kind, s.reason);
    else if (!q.required) continue;
    else if (s.state === "empty") add(q.key, kind, "未回答");
    else if (s.state === "placeholder") add(q.key, kind, s.reason);
    else if (s.state === "omakase" && !q.allowOmakase)
      add(q.key, kind, "この項目は「おまかせ」にできません。事実か公開の条件なので、今回の値を書いてください");
  }
  const ok = (key) => (st[key]?.state === "ok" ? st[key].value : undefined);
  const eff = (key) => ok(key) ?? getPointer(brief, key);
  const conflicts = [];
  const conflict = (keys, reason) => {
    if (keys.every((k) => Q.byKey[k])) conflicts.push({ keys, reason });
  };
  const photo = ok("intake.photo-source");
  if (photo?.includes("none") && photo.length > 1) conflict(["intake.photo-source"], "「写真は使わない」と他の選択が同時に選ばれています");
  const count = eff("/count"),
    white = eff("/whiteCount"),
    tones = eff("/policy/requiredTones");
  if (Number.isInteger(count) && Number.isInteger(white) && white > count)
    conflict(["/whiteCount", "/count"], `白い背景の案（${white}）が案の数（${count}）より多くなっています`);
  if (Number.isInteger(count) && Array.isArray(tones) && tones.length > count)
    conflict(["/policy/requiredTones", "/count"], `必ず入れる配色（${tones.length} 系統）が案の数（${count}）より多くなっています`);
  if (ok(STYLE_PATH)?.some((t) => PHOTO_STYLE.test(t)) && same(photo, ["none"]))
    conflict([STYLE_PATH, "intake.photo-source"], "写真の様式を希望していますが、写真は使わない回答です");
  for (const c of conflicts) for (const k of c.keys) add(k, "conflict", c.reason);
  const order = Q.questions.map((q) => q.key);
  const list = [...items].map(([key, v]) => ({ key, ...v })).sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
  return { st, items: list, unresolved: list.map((i) => i.key), conflicts, readback, styleProposalNeeded: styleNeed(Q, st, dir) };
}

// 様式が未指定・おまかせ・雰囲気語だけのときに、提案の根拠（basis）を返す（様式が決まるまで提案する）。
function styleNeed(Q, st, dir) {
  if (!Q.byKey[STYLE_PATH]) return null;
  const s = st[STYLE_PATH];
  if (s.state === "mismatch" || s.state === "invalid" || (s.state === "ok" && s.source === "proposal")) return null;
  const vague = s.state === "ok" ? s.value.filter((t) => VAGUE.test(t.trim())) : [];
  if (s.state === "ok" && vague.length < s.value.length) return null;
  const doc = dir ? readOptional(path.join(dir, PROPOSALS_FILE)) : undefined;
  const reason = Array.isArray(doc?.chosen)
    ? doc.chosen.length
      ? "pending-apply"
      : "pending-choice"
    : s.state === "omakase"
      ? "omakase"
      : s.state === "ok"
        ? "vague"
        : "unspecified";
  const texts = (key) => (st[key]?.state === "ok" ? strings(st[key].value) : []);
  const val = (key) => (st[key]?.state === "ok" ? st[key].value : null);
  const photo = val("intake.photo-source");
  return {
    reason,
    basis: {
      moodWords: [...new Set([...texts("intake.style-mood"), ...vague.map((t) => t.trim())])],
      references: texts("intake.style-references"),
      avoid: texts("intake.style-avoid"),
      purposeRefs: ["/purpose/audience", "/purpose/benefit", "/purpose/action"].filter((k) => st[k]?.state === "ok"),
      materials: {
        photosAvailable: photo ? photo.some((v) => v === "catalog" || v === "new") : null,
        photoSources: photo,
        logo: val("intake.logo"),
        distribution: val("intake.distribution"),
      },
    },
  };
}

function loadCase(dir) {
  dir = outsidePlugin(dir, "案件フォルダ");
  const file = path.join(dir, "intake.json");
  if (!fs.existsSync(file)) throw Error("intake.json がありません。先に intake-apply で一括回答を反映してください: " + dir);
  const rec = readJSON(file);
  const v = validator(FILES.intake);
  if (!v(rec)) throw Error("intake.json が schema に合いません: " + ajv.errorsText(v.errors));
  const brief = readOptional(path.join(dir, "brief.json")) ?? {};
  return { dir, rec, brief, Q: questions(rec.preset) };
}

function whenText(Q, w) {
  const q = Q.byKey[w.key];
  const label = q?.label ?? w.key;
  const opt = (v) => q?.options?.find((o) => o.value === v)?.label ?? v;
  if ("equals" in w) return `（「${label}」が「${opt(w.equals)}」の場合だけ）`;
  if ("includes" in w) return `（「${label}」で「${opt(w.includes)}」を選んだ場合だけ）`;
  const words = String(w.anyMatch ?? w.anyNotMatch).split("|").join("・");
  return "anyMatch" in w ? `（「${label}」に${words}などを含む場合だけ）` : `（「${label}」に${words}以外を含む場合だけ）`;
}
const cell = (s) => String(s).replace(/\|/g, "｜").replace(/\r?\n/g, " ");

// 全質問を 1 枚にした一括回答シートと、回答を書き込む JSON の雛形を作る。
function template(opts = {}) {
  const Q = questions(opts.preset ?? null);
  const prefillIn = input(opts.prefill, "--prefill") ?? {};
  if (!isObj(prefillIn)) throw Error("--prefill は {キー: {value, source}} の形にしてください");
  const known = {},
    prefillRejected = [];
  for (const [k, e0] of Object.entries(prefillIn)) {
    const key = keyFor(Q, k);
    if (!key) throw Error("prefill に未知の質問キーがあります: " + k);
    const e = isObj(e0) && "value" in e0 ? e0 : { value: e0 };
    const source = e.source ?? "answer";
    if (!["answer", "document"].includes(source)) throw Error(`prefill の出典は answer か document だけです: ${k}`);
    const q = Q.byKey[key];
    if (isReadback(q)) {
      prefillRejected.push({ key, reason: "確定事実の確認は、一覧を見てから答えます" });
      continue;
    }
    const n = normalize(Q, q, e.value, Q.initial);
    if (n.state === "ok" || n.state === "skip" || (n.state === "omakase" && q.allowOmakase))
      known[key] = { value: e.value, source, shown: n.state === "ok" ? show(q, n.value) : n.state === "skip" ? "該当なし" : "おまかせ" };
    else if (n.state !== "empty")
      prefillRejected.push({ key, value: e.value, reason: n.reason ?? "この項目は「おまかせ」にできません" });
  }
  const sugIn = input(opts.suggestions, "--suggestions");
  const entries =
    sugIn === undefined
      ? []
      : Array.isArray(sugIn)
        ? sugIn.map((e) => [e?.key ?? e?.id ?? e?.path, e])
        : Object.entries(isObj(sugIn.suggestions) ? sugIn.suggestions : sugIn);
  const hints = {},
    suggested = {},
    suggestionsIgnored = [];
  for (const [k, e] of entries) {
    if (!isObj(e)) continue;
    const key = keyFor(Q, k) ?? keyFor(Q, e.path) ?? (typeof e.path === "string" ? keyFor(Q, "/" + e.path) : null);
    if (!key) {
      suggestionsIgnored.push(String(k));
      continue;
    }
    const q = Q.byKey[key];
    if (typeof e.text === "string" && e.text.trim()) (hints[key] ??= []).push(e.text.trim());
    // 事実（mustFact）には前回の値を記入しない（E2）。好みだけを「参考・要確認」として記入する。
    const v = e.labels ?? e.value;
    if (!q.mustFact && !known[key] && meaningful(v) && normalize(Q, q, v, Q.initial).state === "ok")
      suggested[key] = { value: clone(v), source: "suggestion", reconfirm: true };
  }
  const draft = {
    answers: Object.fromEntries(Object.entries(known).map(([k, v]) => [k, { value: v.value, source: v.source }])),
    skipped: [],
  };
  const ev = evaluate(Q, draft, Q.initial, null);
  const lines = [
    "# チラシ制作のヒアリング（一括回答シート）",
    "",
    "分かる項目に、一度にまとめて答えてください。分からない項目は空欄で構いません。足りない点と食い違う点だけを、あとで 1 回にまとめて確認します。",
    "",
    "- 日時・会場・料金・申込先などの事実は、推測で埋めず、決まっていなければ空欄にしてください。",
    "- （おまかせ可）の項目は「おまかせ」と書けます。（該当なしは「なし」）の項目は、当てはまらなければ「なし」と書いてください。",
    "- 「参考」と書いた内容は前回までの傾向です。今回の希望として確かめてから答えてください。",
    "",
  ];
  if (Q.preset)
    lines.push(`preset「${Q.preset.id}」を使います。「前回の値」は前の案件の値です。今回も同じかを必ず確かめてください（確かめるまで紙面には使いません）。`, "");
  const knownRows = Q.questions.filter((q) => known[q.key]);
  if (knownRows.length)
    lines.push(
      "## 確認のみ（依頼文や資料から読み取った内容）",
      "",
      "違っていれば、その項目だけ直してください。",
      "",
      "| 項目 | 内容 | 出典 |",
      "|---|---|---|",
      ...knownRows.map((q) => `| ${cell(q.label)} | ${cell(known[q.key].shown)} | ${SOURCE_LABEL[known[q.key].source]} |`),
      "",
    );
  const listed = [];
  let no = 0;
  const detail = (q) => {
    const out = [];
    if (q.why) out.push(`- 理由: ${q.why}`);
    const rejected = prefillRejected.find((r) => r.key === q.key);
    if (rejected && "value" in rejected) out.push(`- 資料から読み取った値（このままでは使えません。${rejected.reason}）: ${strings(rejected.value).join("・")}`);
    if (q.options) out.push(`- 選択肢: ${q.options.map((o) => o.label).join(" / ")}`);
    if (q.example) out.push(q.example.startsWith("例") ? `- ${q.example}` : `- 例: ${q.example}`);
    const prev = previousOf(Q, q);
    const init = q.briefPath ? getPointer(Q.initial, q.briefPath) : undefined;
    if (meaningful(prev) && (q.required || !q.briefPath)) out.push(`- 前回の値（今回も同じか確かめてください）: ${show(q, prev)}`);
    else if (meaningful(init))
      out.push(
        q.required
          ? `- 初期値（このままでよければ同じ値を書いてください）: ${show(q, init)}`
          : `- 初期値（空欄ならこのまま${meaningful(prev) ? "。preset の値" : ""}）: ${show(q, init)}`,
      );
    if (hints[q.key]) out.push(...hints[q.key].map((t) => (/参考/.test(t) ? `- ${t}` : `- 前回までの傾向（参考・要確認）: ${t}`)));
    else if (suggested[q.key]) out.push(`- 前回までの傾向（参考・要確認）: ${show(q, suggested[q.key].value)}`);
    return out;
  };
  for (const g of Q.groups) {
    const qs = Q.questions.filter((q) => q.group === g.id && !q.partOf && !isReadback(q) && !known[q.key] && ev.st[q.key].applies !== false);
    if (!qs.length) continue;
    lines.push(`## ${g.title}`, "");
    for (const q of qs) {
      no++;
      const tags = [
        q.required && !q.askWhen ? "（必須）" : "",
        q.askWhen && ev.st[q.key].applies !== true ? whenText(Q, q.askWhen) : "",
        q.allowOmakase ? "（おまかせ可）" : "",
        q.allowSkip ? "（該当なしは「なし」）" : "",
      ].join("");
      listed.push({ no: `Q${no}`, key: q.key, id: q.id, label: q.label, mustFact: !!q.mustFact, conditional: !!q.askWhen });
      lines.push(`### Q${no}. ${q.label}${tags}`, "", q.prompt, "", ...detail(q));
      Q.questions
        .filter((c) => c.partOf === q.id && !known[c.key])
        .forEach((c, i) => {
          const sub = `Q${no}-${i + 1}`;
          listed.push({ no: sub, key: c.key, id: c.id, label: c.label, mustFact: !!c.mustFact, conditional: !!c.askWhen });
          lines.push(`- ${sub}. ${c.label}: ${c.prompt}${c.example ? `（例: ${c.example}）` : ""}`);
        });
      lines.push("");
    }
  }
  const skeleton = {
    originalRequest: "",
    preset: Q.preset?.id ?? null,
    answers: Object.fromEntries(
      Q.questions
        .filter((q) => !isReadback(q) && (known[q.key] || ev.st[q.key].applies !== false))
        .map((q) => [q.key, known[q.key] ? draft.answers[q.key] : (suggested[q.key] ?? null)]),
    ),
  };
  const markdown = lines.join("\n");
  let files;
  if (opts.out) {
    const out = outsidePlugin(opts.out, "一括回答シート");
    fs.mkdirSync(path.dirname(out), { recursive: true });
    fs.writeFileSync(out, markdown + "\n");
    const answersFile = out.replace(/\.[^./\\]+$/, "") + ".answers.json";
    writeJSON(answersFile, skeleton);
    files = { markdown: out, answers: answersFile };
  }
  return { markdown, answers: skeleton, questions: listed, prefillRejected, suggestionsIgnored, ...(files ? { files } : {}) };
}

const upsertSkip = (list, key, reason) => {
  const i = list.findIndex((s) => s.path === key);
  if (i >= 0) list[i] = { path: key, reason };
  else list.push({ path: key, reason });
};
const removeSkip = (list, key) => {
  const i = list.findIndex((s) => s.path === key);
  if (i >= 0) list.splice(i, 1);
};

// 一括回答を検査し、brief.json と intake.json を書く。空欄は前回までの回答を消さない。
function apply(dir, answersInput) {
  dir = outsidePlugin(dir, "案件フォルダ");
  const briefFile = path.join(dir, "brief.json");
  if (!fs.existsSync(briefFile)) throw Error("brief.json がありません。先に init で案件フォルダを作ってください: " + dir);
  const brief = readJSON(briefFile);
  const raw = input(answersInput, "--answers");
  if (!isObj(raw)) throw Error("--answers は {キー: 値} か {originalRequest, preset, answers, skipped} の形で渡してください");
  const envelope = isObj(raw.answers);
  const map = envelope ? raw.answers : raw;
  const file = path.join(dir, "intake.json");
  const prev = readOptional(file);
  if (prev && !validator(FILES.intake)(prev)) throw Error("intake.json が schema に合いません: " + ajv.errorsText(validator(FILES.intake).errors));
  const wanted = [...new Set([envelope ? raw.preset : undefined, brief.preset?.id].filter(meaningful).map((n) => presetInfo(n).id))];
  if (wanted.length > 1) throw Error("preset が食い違っています: " + wanted.join(" / "));
  const presetId = prev ? prev.preset : (wanted[0] ?? null);
  if (prev && wanted.length && wanted[0] !== presetId) throw Error(`preset は最初の回答のとき（${presetId ?? "なし"}）から変えられません`);
  const Q = questions(presetId);
  const request = envelope && typeof raw.originalRequest === "string" ? raw.originalRequest.trim() : "";
  if (prev?.originalRequest && request && request !== prev.originalRequest)
    throw Error("最初の依頼文（originalRequest）は変えられません。依頼そのものが変わったときは新しい案件にしてください");
  const round = prev ? prev.rounds + 1 : 1;
  const answers = clone(prev?.answers ?? {}),
    skipped = clone(prev?.skipped ?? []);
  const problems = [],
    followUps = [];
  const incoming = [];
  for (const [k, entry] of Object.entries(map)) {
    const key = keyFor(Q, k);
    if (!key) throw Error("未知の質問キーです: " + k + "（intake-questions.json の id か briefPath を使ってください）");
    const q = Q.byKey[key];
    const e = isObj(entry) && "value" in entry ? entry : { value: entry };
    if (normalize(Q, q, e.value, brief).state === "empty") continue;
    const source = e.source ?? "answer";
    if (source === "suggestion") {
      problems.push({ key, reason: "前回までの傾向（参考）のままです。今回の希望として確かめ、source を外すか answer にしてください" });
      continue;
    }
    if (!SOURCES.includes(source)) {
      problems.push({ key, reason: "未知の出典です: " + source });
      continue;
    }
    if (key === STYLE_PATH ? !["answer", "document", "proposal"].includes(source) : source === "proposal") {
      problems.push({
        key,
        reason: key === STYLE_PATH ? "様式の出典は answer（利用者が指定）・document（資料に明示）・proposal（提案から選択）だけです" : "proposal は様式（/stylePreferences）にだけ使えます",
      });
      continue;
    }
    incoming.push({ key, q, value: e.value, source, note: typeof e.note === "string" && e.note.trim() ? e.note.trim() : undefined });
  }
  const sig = (key) => (answers[key] ? JSON.stringify(canon(answers[key].value)) : skipped.some((s) => s.path === key) ? "skip" : "");
  const factKeys = Q.questions.filter(isFact).map((q) => q.key);
  const before = Object.fromEntries(factKeys.map((k) => [k, sig(k)]));
  const readbackBefore = prev ? evaluate(Q, prev, brief, dir).readback : false;
  for (const it of incoming) {
    const n = normalize(Q, it.q, it.value, brief);
    if (n.state === "skip") {
      delete answers[it.key];
      upsertSkip(skipped, it.key, "該当なし");
      continue;
    }
    let source = n.state === "placeholder" ? "placeholder" : it.source;
    if (source === "answer" && n.state === "ok" && Q.preset && it.key !== STYLE_PATH && meaningful(previousOf(Q, it.q)) && same(previousOf(Q, it.q), n.value))
      source = "preset-reconfirmed";
    answers[it.key] = { value: n.state === "ok" ? n.value : it.value, source, round, ...(it.note ? { note: it.note } : {}) };
    removeSkip(skipped, it.key);
  }
  for (const s of envelope && Array.isArray(raw.skipped) ? raw.skipped : []) {
    const key = keyFor(Q, s?.path);
    if (!key) throw Error("skipped に未知の質問キーがあります: " + s?.path);
    if (!Q.byKey[key].allowSkip) {
      problems.push({ key, reason: "この項目は省けません" });
      continue;
    }
    delete answers[key];
    upsertSkip(skipped, key, typeof s.reason === "string" && s.reason.trim() ? s.reason.trim() : "該当なし");
  }
  // 確定事実の確認は、事実が揃った一覧を見た後の回でだけ受け付ける。事実が変われば確認をやり直す。
  const changed = factKeys.filter((k) => before[k] !== sig(k));
  for (const q of Q.questions.filter(isReadback)) {
    const got = incoming.some((it) => it.key === q.key);
    if (got && (changed.length || !readbackBefore)) {
      problems.push({ key: q.key, reason: "確定事実の一覧を見てから答えてください" + (changed.length ? `（この回で変わった事実: ${changed.join(", ")}）` : "") });
      if (prev?.answers?.[q.key] && !changed.length) answers[q.key] = prev.answers[q.key];
      else delete answers[q.key];
    } else if (changed.length && answers[q.key]) {
      delete answers[q.key];
      followUps.push("事実が変わったため、確定事実の確認をやり直します");
    }
  }
  const rec = { version: 1, originalRequest: prev?.originalRequest || request, preset: Q.preset?.id ?? null, rounds: round, answers, unresolved: [], skipped };
  const ev = evaluate(Q, rec, brief, dir);
  rec.unresolved = ev.unresolved;
  const written = [];
  const put = (ptr, v) => {
    if (same(getPointer(brief, ptr), v)) return;
    setPointer(brief, ptr, v);
    written.push(ptr);
  };
  for (const q of Q.questions) {
    if (!q.briefPath) continue;
    const s = ev.st[q.key];
    if (isReadback(q)) put(q.briefPath, s.applies === true && s.state === "ok" && s.value === true);
    else if (s.applies === false) continue;
    else if (s.state === "ok") put(q.briefPath, q.answerType === "page-size" ? { ...brief.page, ...s.value } : s.value);
    else if (s.state === "skip" && getPointer(brief, q.briefPath) !== undefined) {
      deletePointer(brief, q.briefPath);
      written.push(q.briefPath);
    }
  }
  const v = validator(FILES.intake);
  if (!v(rec)) throw Error("intake.json の形が不正です: " + ajv.errorsText(v.errors));
  writeJSON(file, rec);
  writeJSON(briefFile, brief);
  const concepts = readOptional(path.join(dir, "concepts.json"));
  if (Array.isArray(concepts?.variants) && Number.isInteger(brief.count) && concepts.variants.length !== brief.count)
    followUps.push(`concepts.json の案の数（${concepts.variants.length}）が brief.count（${brief.count}）と違います。制作の段で案の枠を作り直してください`);
  if (ev.styleProposalNeeded) followUps.push(`様式の提案が必要です（${ev.styleProposalNeeded.reason}）。intake-residual の styleProposalNeeded.basis を使ってください`);
  return {
    rounds: round,
    written,
    unresolved: ev.unresolved,
    problems,
    skipped: skipped.map((s) => s.path),
    followUps,
    styleProposalNeeded: ev.styleProposalNeeded,
  };
}

const STYLE_REASON = {
  unspecified: "様式の指定がまだありません",
  omakase: "様式はおまかせと伺いました",
  vague: "様式を雰囲気の言葉で伺いました",
  "pending-choice": "お見せした様式の提案から、まだ選ばれていません",
  "pending-apply": "選ばれた様式の提案が、まだ回答に反映されていません",
};

// 不足・矛盾・読み返し・様式提案の要否だけを返す。
function residual(dir) {
  const { Q, rec, brief, dir: d } = loadCase(dir);
  const ev = evaluate(Q, rec, brief, d);
  const items = ev.items.map((i) => ({ key: i.key, id: Q.byKey[i.key].id, kind: i.kind, label: Q.byKey[i.key].label, prompt: Q.byKey[i.key].prompt, reason: i.reason }));
  const lines = [`# 追加で確かめたいこと（${items.length} 件）`, ""];
  const asks = items.filter((i) => i.kind !== "readback");
  if (asks.length) {
    lines.push("足りない点と食い違う点だけを伺います。既にいただいた回答は聞き直しません。", "");
    asks.forEach((i, n) => lines.push(`${n + 1}. **${i.label}**: ${i.prompt}（${i.reason}）`));
    lines.push("");
  }
  if (items.some((i) => i.kind === "readback")) {
    const rows = Q.questions.filter(isFact).map((q) => {
      const s = ev.st[q.key];
      return `| ${cell(q.label)} | ${cell(s.state === "skip" ? "該当なし" : show(q, s.value))} | ${s.state === "skip" ? "該当なし" : SOURCE_LABEL[rec.answers[q.key]?.source] ?? ""} |`;
    });
    const rq = Q.questions.find(isReadback);
    lines.push("## 確定事実の確認", "", rq.prompt, "", "| 項目 | 紙面に載せる内容 | 出典 |", "|---|---|---|", ...rows, "");
  }
  if (ev.styleProposalNeeded)
    lines.push("## 見た目の様式", "", `${STYLE_REASON[ev.styleProposalNeeded.reason]}。いただいた言葉と目的から 2〜3 案の様式を作ってお見せします。`, "");
  if (!items.length && !ev.styleProposalNeeded) lines.push("追加で確かめることはありません。");
  return {
    markdown: lines.join("\n"),
    json: { round: rec.rounds + 1, items, skeleton: { answers: Object.fromEntries(items.map((i) => [i.key, null])) } },
    count: items.length,
    styleProposalNeeded: ev.styleProposalNeeded,
    done: !items.length && !ev.styleProposalNeeded,
  };
}

// 必須の項目の未解決・仮置きが残っていれば止める。様式の未指定では止めない（様式は事実ではない）。
function assertResolved(dir) {
  const { Q, rec, brief, dir: d } = loadCase(dir);
  const ev = evaluate(Q, rec, brief, d);
  const placeholders = Q.questions
    .filter((q) => q.mustFact && ev.st[q.key].applies !== false && rec.answers[q.key]?.source === "placeholder")
    .map((q) => q.key);
  const bad = [...new Set([...rec.unresolved, ...ev.unresolved, ...placeholders])];
  if (bad.length)
    throw Error("ヒアリングが終わっていません（intake-residual で残りを確かめてください）: " + bad.map((k) => `${Q.byKey[k]?.label ?? k}（${k}）`).join("、"));
  return { ok: true, rounds: rec.rounds, checked: Q.questions.filter((q) => ev.st[q.key].applies === true).length };
}

module.exports = { template, apply, residual, assertResolved, questions, outsidePlugin, getPointer, STYLE_PATH };
