### 手順2: Automated Code Scanning

Run these checks in parallel:

#### 2.1 Secrets & Credentials Detection
```bash
# Search for hardcoded secrets
grep -rn --include="*.{ts,tsx,js,jsx,py,go,java,rb,php,env}" \
  -E "(password|secret|api_key|apikey|token|private_key|aws_access|DATABASE_URL)\s*[:=]\s*['\"][^'\"]{8,}" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Check for .env files committed
git ls-files | grep -E "\.env($|\.)" | grep -v ".env.example"

# Check .gitignore includes env files
grep -q "\.env" .gitignore 2>/dev/null && echo "OK: .env in .gitignore" || echo "CRITICAL: .env NOT in .gitignore"

# Check git history for leaked secrets
git log --all --diff-filter=A --name-only --pretty=format: | grep -E "\.env($|\.)" | sort -u
```

#### 2.2 SQL Injection & Query Safety
```bash
# Find raw SQL queries with string interpolation
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "(query|execute|raw)\s*\(\s*[`'\"].*\$\{" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Find string concatenation in SQL
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "SELECT.*\+.*FROM|INSERT.*\+.*INTO|UPDATE.*\+.*SET|DELETE.*\+.*FROM" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null
```

#### 2.3 XSS Vulnerability Detection
```bash
# Find dangerouslySetInnerHTML usage
grep -rn --include="*.{ts,tsx,js,jsx}" \
  "dangerouslySetInnerHTML" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Find innerHTML usage
grep -rn --include="*.{ts,tsx,js,jsx}" \
  "\.innerHTML\s*=" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Find eval usage
grep -rn --include="*.{ts,tsx,js,jsx,py}" \
  -E "\beval\s*\(|new\s+Function\s*\(" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Find document.write
grep -rn --include="*.{ts,tsx,js,jsx}" \
  "document\.write" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null
```

#### 2.4 Authentication & Session Security
```bash
# Check for localStorage token storage
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "localStorage\.(set|get)Item.*token" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Check JWT alg:none vulnerability
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "algorithms.*none|alg.*none" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Check session/cookie security attributes
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "Set-Cookie|cookie" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null
```

#### 2.5 Command Injection
```bash
# Find OS command execution
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "exec\(|execSync\(|spawn\(|child_process" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Python command injection
grep -rn --include="*.py" \
  -E "os\.system\(|subprocess\.(call|run|Popen)\(" \
  --exclude-dir={node_modules,.git,dist,build,.next,venv,.venv} . 2>/dev/null
```

#### 2.6 Dependency Vulnerabilities
```bash
# pnpm audit
pnpm audit --json 2>/dev/null | head -50

# Or pnpm
ppnpm audit --json 2>/dev/null | head -50

# Check for outdated packages
pnpm outdated 2>/dev/null | head -20
```

#### 2.7 Security Headers Check
```bash
# Check for security header configuration
grep -rn --include="*.{ts,tsx,js,jsx,json}" \
  -E "Content-Security-Policy|X-Frame-Options|X-Content-Type-Options|Strict-Transport-Security|Referrer-Policy|Permissions-Policy" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Check next.config for headers
cat next.config.* 2>/dev/null | grep -A5 "headers"

# Check vercel.json for headers
cat vercel.json 2>/dev/null | grep -A5 "headers"
```

#### 2.8 File Upload Security
```bash
# Find file upload handling
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "multer|formidable|busboy|multipart|file.*upload|Upload" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Check for file type validation
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "mimetype|mime-type|file\.type|extension" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null
```

#### 2.9 API Security
```bash
# Find unprotected API routes
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "export.*(GET|POST|PUT|DELETE|PATCH)" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Check for rate limiting
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "rateLimit|rate-limit|throttle|limiter" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Check for CORS configuration
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "cors|Access-Control-Allow-Origin" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null
```

#### 2.10 Database Security (Cloudflare D1 / SQLite)

D1 (SQLite) にはデータベース側の行レベルアクセス制御が存在しない。アクセス制御はアプリ層 (API ハンドラでのセッション確認と所有者チェック) が唯一の防御線になるため、そこを重点的に検査する。

```bash
# List tables defined in migrations (each one needs an app-layer owner check)
grep -rn --include="*.sql" \
  "CREATE TABLE" . 2>/dev/null

# Check that API handlers verify the session before touching D1
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "auth\.api\.getSession|getSession\(|requireUser|requireSession" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Find D1 queries that filter only by id (missing an owner/tenant condition)
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "DB\.prepare\(|db\.(select|update|delete)\(" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null

# Check for raw SQL string interpolation (SQL injection risk)
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "prepare\(\`.*\\\$\{" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null
```

#### 2.11 Source Map & Debug Mode
```bash
# Check for source maps in production config
grep -rn "sourcemap\|sourceMap\|devtool" \
  --include="*.{ts,js,json}" \
  --exclude-dir={node_modules,.git} . 2>/dev/null

# Check for debug mode
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "debug\s*[:=]\s*true|NODE_ENV.*development" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null
```

#### 2.12 Open Redirect Detection
```bash
# Find redirect with user input
grep -rn --include="*.{ts,tsx,js,jsx}" \
  -E "redirect\(|window\.location\s*=|location\.href\s*=" \
  --exclude-dir={node_modules,.git,dist,build,.next} . 2>/dev/null
```

