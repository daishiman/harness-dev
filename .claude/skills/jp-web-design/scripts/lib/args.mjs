// CLI引数の共通解析。入力の誤りは UsageError として投げ、failCli が usage を添えて終了コード2にする。

export class UsageError extends Error {}

// booleans: { '--json': 'json' } / values: { '--mode': 'mode' }（--mode=value 形式）。未知の --flag は入力エラー。
export function parseArgs(argv, { positionals, booleans = {}, values = {} }) {
  const args = []
  const options = {}
  for (const arg of argv) {
    if (!arg.startsWith('--')) { args.push(arg); continue }
    const equals = arg.indexOf('=')
    const name = equals < 0 ? arg : arg.slice(0, equals)
    if (equals < 0 && Object.hasOwn(booleans, name)) options[booleans[name]] = true
    else if (equals >= 0 && Object.hasOwn(values, name)) options[values[name]] = arg.slice(equals + 1)
    else throw new UsageError(`unknown option: ${arg}`)
  }
  if (args.length !== positionals) throw new UsageError(`expected ${positionals} positional argument(s), got ${args.length}`)
  return { args, options }
}

export function oneOf(flag, value, allowed) {
  if (!allowed.includes(value)) throw new UsageError(`${flag} must be one of: ${allowed.join(', ')}`)
  return value
}

export function failCli(error, usage) {
  console.error(error.message)
  if (error instanceof UsageError) console.error(usage)
  process.exitCode = 2
}
