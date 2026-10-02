@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
rem =====================================================
rem  開発環境セットアップ (Windows用)
rem  Node.js と pnpm をインストールし、Claude Code / Codex と
rem  Cloudflare の連携(MCP)も設定します
rem  ダブルクリックするだけでOKです
rem  v1.11.0
rem =====================================================

echo.
echo ===============================================
echo   開発環境セットアップ (Windows)
echo   Node.js と pnpm を準備します
echo ===============================================
echo.

rem --- ステップ 0/4: 実行環境の事前確認 --------------------------
rem このスクリプトは PowerShell 経由で pnpm を取得する。使えない環境を先に名指しする。
set "AIDD_KIT_DIR=%~dp0"
rem 起動時のカレントフォルダ。「利用者がどのプロジェクトの中でこれを実行したか」は
rem .mcp.json の残骸を見に行くときに必要になるので控えておく。
set "AIDD_INVOKE_DIR=%CD%"
rem セットアップの最終確認状態。存在だけで ready とは扱わず、
rem attempted / registered / auth_pending / ready / failed を記録する。
rem 置き場所を AIDD_TARGET_HOME に追従させないのは、MCP の登録先が常に
rem user scope(そのパソコンの利用者ひとりに1つ)だから。キット本体を
rem project scope へ入れることはあっても、MCP はそれとは独立している。
set "SETUP_STAMP=%USERPROFILE%\.claude\aidd-agent-kit.setup-env"
set "AIDD_LOG=%TEMP%\aidd-agent-kit-setup-env.log"
type nul > "%AIDD_LOG%" 2>nul
call :RECORD_SETUP_STATE attempted
call :PRECHECK_ENV
if errorlevel 1 goto :fail
call :LOAD_NODE_MIN_MAJOR
if errorlevel 1 goto :fail

set "PNPM_HOME=%LOCALAPPDATA%\pnpm"
set "PATH=%PNPM_HOME%;%PATH%"

rem --- ステップ 1/4: pnpm のインストール -------------------------
where pnpm >nul 2>nul
if %errorlevel%==0 (
    call :GET_TOOL_VERSION pnpm PNPM_VERSION
    if not !errorlevel!==0 (
        echo [エラー] pnpm コマンドは見つかりましたが、正常に実行できません。
        echo pnpm のインストールを修復してから、もう一度実行してください。
        goto :fail
    )
    echo ^(1/4^) pnpm はインストール済みです ^(!PNPM_VERSION!^)
) else (
    echo ^(1/4^) pnpm をインストールしています^(1〜2分^)...
    rem ネットワーク取得物を直接iexせず、pnpm公式repoのimmutable commitと
    rem SHA-256を照合してから実行する。公式installer自身もpackage integrityを検証する。
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; $uri='https://raw.githubusercontent.com/pnpm/get.pnpm.io/11faaa4bb062a5cdac4c22d1a36645d6a3692b82/install.ps1'; $expected='B5E355310CC3301DA60B4B6A42DF9E0EA38C59A46F783C22217919578D1E895D'; $installer=Join-Path $env:TEMP ('aidd-pnpm-install-' + [Guid]::NewGuid().ToString('N') + '.ps1'); try { Invoke-WebRequest -Uri $uri -UseBasicParsing -OutFile $installer; $actual=(Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash; if ($actual -ne $expected) { throw 'pnpm installer integrity check failed' }; & $installer } finally { Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue }"
    if errorlevel 1 (
        echo [エラー] pnpm公式installerの取得・完全性確認・実行に失敗しました。
        echo 完全性を確認できないスクリプトは実行していません。
        goto :fail
    )
    set "PATH=%PNPM_HOME%;%PATH%"
    call :GET_TOOL_VERSION pnpm PNPM_VERSION
    if not !errorlevel!==0 (
        echo [エラー] pnpm のインストールに失敗しました。
        echo インターネット接続を確認して、もう一度実行してください。
        echo 社内ネットワークの通信制限が原因の場合があります。
        echo 解決しないときは、この画面のままIT担当者にお見せください。
        goto :fail
    )
    echo       pnpm !PNPM_VERSION! をインストールしました
)

rem --- ステップ 2/4: Node.js のインストール ----------------------
echo (2/4) Node.js を確認しています...
where node >nul 2>nul
if %errorlevel%==0 (
    call :GET_TOOL_VERSION node NODE_VERSION
    if not !errorlevel!==0 (
        echo [エラー] Node.js コマンドは見つかりましたが、正常に実行できません。
        echo Node.js のインストールを修復してから、もう一度実行してください。
        goto :fail
    )
    echo       Node.js はインストール済みです ^(!NODE_VERSION!^)
    call :ENSURE_NODE_OK
    if errorlevel 1 goto :fail
) else (
    echo       Node.js をインストールしています^(2〜3分^)...
    call pnpm env use --global lts
    set "PATH=%PNPM_HOME%;%PATH%"
    call :GET_TOOL_VERSION node NODE_VERSION
    if not !errorlevel!==0 (
        echo [エラー] Node.js のインストールに失敗しました。
        echo この画面のまま導入支援の担当者にお見せください。
        goto :fail
    )
    echo       Node.js !NODE_VERSION! をインストールしました
    call :ENSURE_NODE_OK
    if errorlevel 1 goto :fail
)

rem --- ステップ 3/4: AI開発ツールと Cloudflare の連携(MCP) ---------
echo (3/4) Claude Code / Codex と Cloudflare の連携を設定しています...
set /a MCP_FAILURES=0
set /a MCP_PENDING=0
set /a MCP_REGISTERED=0
set /a MCP_READY=0
set /a MCP_SKIPPED=0
set /a CLAUDE_SKIPPED=0
set /a CODEX_SKIPPED=0

echo       MCPの user scope^(どのフォルダから使うか^)と
echo       Cloudflare OAuth権限^(Account/read/write^)は別物です。
echo       docsは認証不要。それ以外は必要時に最小権限だけ認可してください。

where claude >nul 2>nul
if %errorlevel%==0 (
    call :CONFIGURE_CLAUDE_MCP "cloudflare-bindings" "https://bindings.mcp.cloudflare.com/mcp"
    call :CONFIGURE_CLAUDE_MCP "cloudflare-docs" "https://docs.mcp.cloudflare.com/mcp"
    call :CONFIGURE_CLAUDE_MCP "cloudflare-observability" "https://observability.mcp.cloudflare.com/mcp"
) else (
    echo       Claude Code: スキップ^(コマンドが見つかりません^)
    set /a MCP_SKIPPED+=1
    set /a CLAUDE_SKIPPED=1
)
where codex >nul 2>nul
if %errorlevel%==0 (
    call :CONFIGURE_CODEX_MCP "cloudflare-bindings" "https://bindings.mcp.cloudflare.com/mcp"
    call :CONFIGURE_CODEX_MCP "cloudflare-docs" "https://docs.mcp.cloudflare.com/mcp"
    call :CONFIGURE_CODEX_MCP "cloudflare-observability" "https://observability.mcp.cloudflare.com/mcp"
) else (
    echo       OpenAI Codex: スキップ^(コマンドが見つかりません^)
    set /a MCP_SKIPPED+=1
    set /a CODEX_SKIPPED=1
)
echo       ^(変更系MCPの権限は、その機能を初めて使う時だけ認証します^)

rem --- project scope の .mcp.json 残骸を見つけて知らせる -----------------
rem このキットは MCP を user scope(ユーザー全体)にだけ登録する。ところが
rem プロジェクト直下に古い .mcp.json が残っていると、Claude Code はそちらを
rem 優先候補として拾い、claude mcp list が [Conflicting scopes] を出す。
rem "type": "sse"(legacy sse)は 410 Gone になる。/sse URL との違いと4分岐
rem (未登録 / 不通 / legacy sse / scope 衝突)の裁定は
rem skills\wrangler\references\mcp-vs-cli-routing.md が正本。
rem 絶対に自動削除しない。.mcp.json はキットの管理外であり、利用者の他の
rem プロジェクトの設定でもある。見つけたことと直し方だけを伝える。
set /a MCP_JSON_WARNED=0
call :WARN_STALE_MCP_JSON "!AIDD_INVOKE_DIR!"
call :WARN_STALE_MCP_JSON "%AIDD_KIT_DIR%.."
if defined AIDD_PROJECT_DIR call :WARN_STALE_MCP_JSON "!AIDD_PROJECT_DIR!"
if !MCP_JSON_WARNED! GTR 0 echo.

rem --- ステップ 4/4: 確認 ---------------------------------------
echo (4/4) 動作確認をしています...
echo.
echo   Node.js: !NODE_VERSION!
echo   pnpm:    !PNPM_VERSION!
echo.
if !MCP_FAILURES! GTR 0 (
    call :RECORD_SETUP_STATE failed
    echo [エラー] Cloudflare MCP の設定または確認に !MCP_FAILURES! 件失敗しました。
    echo 上の失敗内容を確認してから、もう一度実行してください。
    goto :fail
)
if !MCP_SKIPPED! GTR 0 (
    call :RECORD_SETUP_STATE attempted
    echo ===============================================
    echo   基本セットアップ完了 / 一部の連携は未設定
    echo ===============================================
    echo.
    echo Node.js と pnpm の準備は終わりました。
    echo 次のツールが見つからないため、Cloudflare 連携は設定していません:
    if !CLAUDE_SKIPPED!==1 echo   - Claude Code ^(claude^)
    if !CODEX_SKIPPED!==1 echo   - OpenAI Codex ^(codex^)
    echo.
    echo そのツールを使う予定があるなら、導入後にもう一度実行してください。
    echo 使わないのであれば、このままで問題ありません。
    echo.
    call :PAUSE_IF_INTERACTIVE
    exit /b 0
)
if !MCP_PENDING! GTR 0 (
    call :RECORD_SETUP_STATE registered
    echo ===============================================
    echo   基本セットアップ完了 / 変更系MCPは必要時に認証
    echo ===============================================
    echo.
    echo Cloudflare MCPのuser/global登録と、認証不要のdocs接続は完了しました。
    echo bindings変更やobservability調査を初めて行う時に、
    echo エージェントが必要な対象1件だけの認証を案内します。今は認証不要です。
    echo.
    call :PAUSE_IF_INTERACTIVE
    exit /b 0
)
call :RECORD_SETUP_STATE ready
echo ===============================================
echo   セットアップが完全に完了しました！
echo ===============================================
echo.
echo 次にやること:
echo   開いているコマンドプロンプトやターミナルがあれば、
echo   一度閉じて開き直してください。(新しい設定を読み込むためです)
echo.
call :PAUSE_IF_INTERACTIVE
exit /b 0

:WARN_STALE_MCP_JSON
rem %~1 = 調べるフォルダ。存在しない・該当しないときは何も言わない。
set "MCPJ_DIR=%~1"
if not defined MCPJ_DIR exit /b 0
set "MCPJ_FILE=%MCPJ_DIR%\.mcp.json"
if not exist "!MCPJ_FILE!" exit /b 0
%SystemRoot%\System32\findstr.exe /i /r /c:"\"type\"[ ]*:[ ]*\"sse\"" "!MCPJ_FILE!" >nul 2>nul
if errorlevel 1 exit /b 0
if !MCP_JSON_WARNED!==0 (
    echo.
    echo -----------------------------------------------
    echo   [注意] 古い形式の MCP 設定が見つかりました
    echo -----------------------------------------------
    set /a MCP_JSON_WARNED=1
)
echo   !MCPJ_FILE!
echo     このファイルに deprecated transport を強制する type=sse があります。
echo     この形式^(legacy sse^)は 410 Gone になります。
echo     ^(/sse URL と type=sse の違いは skills\wrangler\references\mcp-vs-cli-routing.md^)
echo     また、このプロジェクト用の設定がユーザー全体の設定より優先されるため、
echo     キットが登録した正しい設定が隠れます^([Conflicting scopes] の原因^)。
echo     直し方^(どちらか^):
echo       - URL を https://^<名前^>.mcp.cloudflare.com/mcp に書き換え、"type" を "http" にする
echo       - そのエントリを .mcp.json から削除する^(キットの user scope 設定が使われます^)
echo     ※ この script は .mcp.json を変更しません。git 管理下ならリポジトリの変更として
echo        PR で直し、未追跡なら利用者本人が直してください^(AI エージェントは差分を提示できます^)。
exit /b 0

:RECORD_SETUP_STATE
rem stampには状態と件数だけを書く。token、Account ID、secret、CLI出力は書かない。
set "SETUP_STATE=%~1"
if /i not "!SETUP_STATE!"=="attempted" if /i not "!SETUP_STATE!"=="registered" if /i not "!SETUP_STATE!"=="auth_pending" if /i not "!SETUP_STATE!"=="ready" if /i not "!SETUP_STATE!"=="failed" exit /b 0
if not defined USERPROFILE exit /b 0
for %%P in ("!SETUP_STAMP!") do if not exist "%%~dpP" mkdir "%%~dpP" >nul 2>&1
set "STATE_REGISTERED=0"
set "STATE_PENDING=0"
set "STATE_READY=0"
set "STATE_FAILED=0"
set "STATE_SKIPPED=0"
if defined MCP_REGISTERED set "STATE_REGISTERED=!MCP_REGISTERED!"
if defined MCP_PENDING set "STATE_PENDING=!MCP_PENDING!"
if defined MCP_READY set "STATE_READY=!MCP_READY!"
if defined MCP_FAILURES set "STATE_FAILED=!MCP_FAILURES!"
if defined MCP_SKIPPED set "STATE_SKIPPED=!MCP_SKIPPED!"
set "STATE_TMP=!SETUP_STAMP!.tmp.!RANDOM!.!RANDOM!"
> "!STATE_TMP!" (
    echo schema=2
    echo state=!SETUP_STATE!
    echo attempted=1
    echo registered=!STATE_REGISTERED!
    echo auth_pending=!STATE_PENDING!
    echo ready=!STATE_READY!
    echo failed=!STATE_FAILED!
    echo skipped=!STATE_SKIPPED!
    echo date=!DATE! !TIME!
) 2>nul
move /y "!STATE_TMP!" "!SETUP_STAMP!" >nul 2>nul
exit /b 0

:LOAD_NODE_MIN_MAJOR
set "NODE_MIN_MAJOR="
if not exist "%AIDD_KIT_DIR%NODE_MIN_MAJOR" (
    echo [エラー] キットの NODE_MIN_MAJOR が見つかりません。
    echo キットを再度ダウンロードしてから、もう一度実行してください。
    exit /b 1
)
set /p "NODE_MIN_MAJOR="<"%AIDD_KIT_DIR%NODE_MIN_MAJOR"
echo(!NODE_MIN_MAJOR!| %SystemRoot%\System32\findstr.exe /r /x "[1-9][0-9]*" >nul
if errorlevel 1 (
    echo [エラー] キットの NODE_MIN_MAJOR が正しい数値ではありません。
    echo キットを再度ダウンロードしてから、もう一度実行してください。
    exit /b 1
)
exit /b 0

:ENSURE_NODE_OK
set "NODE_MAJOR=!NODE_VERSION:v=!"
for /f "tokens=1 delims=." %%M in ("!NODE_MAJOR!") do set "NODE_MAJOR=%%M"
echo(!NODE_MAJOR!| %SystemRoot%\System32\findstr.exe /r /x "[0-9][0-9]*" >nul
if errorlevel 1 set "NODE_MAJOR=0"
if !NODE_MAJOR! GEQ !NODE_MIN_MAJOR! exit /b 0

echo       Node.js !NODE_VERSION! は古すぎます ^(v!NODE_MIN_MAJOR! 以上が必要^)。
echo       新しい Node.js を入れています^(2〜3分^)...
call pnpm env use --global lts
set "PATH=%PNPM_HOME%;%PATH%"
call :GET_TOOL_VERSION node NODE_VERSION
if not !errorlevel!==0 set "NODE_VERSION="
set "NODE_MAJOR=!NODE_VERSION:v=!"
for /f "tokens=1 delims=." %%M in ("!NODE_MAJOR!") do set "NODE_MAJOR=%%M"
echo(!NODE_MAJOR!| %SystemRoot%\System32\findstr.exe /r /x "[0-9][0-9]*" >nul
if errorlevel 1 set "NODE_MAJOR=0"
if !NODE_MAJOR! LSS !NODE_MIN_MAJOR! (
    echo.
    echo [エラー] Node.js を v!NODE_MIN_MAJOR! 以上にできませんでした ^(現在: !NODE_VERSION!^)。
    echo         使用中の Node.js:
    where node 2^>nul
    echo         nvm / Volta / asdf などで固定されている可能性があります。
    echo         この画面のまま導入支援の担当者にお見せください。
    exit /b 1
)
echo       Node.js !NODE_VERSION! に更新しました
exit /b 0

:GET_TOOL_VERSION
set "%~2="
set "VERSION_FILE=%TEMP%\aidd-agent-kit-version-!RANDOM!-!RANDOM!.txt"
call %~1 --version >"!VERSION_FILE!" 2>nul
set "VERSION_STATUS=!errorlevel!"
if "!VERSION_STATUS!"=="0" set /p "%~2="<"!VERSION_FILE!"
del /q "!VERSION_FILE!" >nul 2>nul
if not "!VERSION_STATUS!"=="0" exit /b 1
if not defined %~2 exit /b 1
exit /b 0

:REPORT_CLAUDE_MCP_STATUS
set "MCP_NAME=%~1"
set "MCP_URL=%~2"
set "MCP_CHECK_FILE=%~3"
set "MCP_ACTION=%~4"
set "MCP_MATCH=1"
findstr /l /c:"Scope: User config" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
findstr /l /c:"Type: http" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
findstr /l /c:"URL: %MCP_URL%" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
if not "!MCP_MATCH!"=="1" exit /b 1

findstr /i /l /c:"Connected" "%MCP_CHECK_FILE%" >nul
if !errorlevel!==0 (
    echo       Claude Code / %MCP_NAME%: %MCP_ACTION%^(接続ready^)
    set /a MCP_REGISTERED+=1
    set /a MCP_READY+=1
    exit /b 0
)
findstr /i /l /c:"Needs authentication" /c:"Authentication required" /c:"Needs auth" "%MCP_CHECK_FILE%" >nul
if !errorlevel!==0 (
    echo       Claude Code / %MCP_NAME%: 設定済み・認証待ち
    set /a MCP_REGISTERED+=1
    set /a MCP_PENDING+=1
    exit /b 0
)
echo       Claude Code / %MCP_NAME%: 失敗^(接続状態がreadyではありません^)
type "%MCP_CHECK_FILE%"
set /a MCP_FAILURES+=1
exit /b 0

:CONFIGURE_CLAUDE_MCP
set "MCP_NAME=%~1"
set "MCP_URL=%~2"
set "MCP_CHECK_FILE=%TEMP%\aidd-agent-kit-mcp-!RANDOM!-!RANDOM!.txt"

call claude mcp get "%MCP_NAME%" >"%MCP_CHECK_FILE%" 2>&1
set "MCP_GET_STATUS=!errorlevel!"
if "!MCP_GET_STATUS!"=="0" (
    set "MCP_MATCH=1"
    findstr /l /c:"Scope: User config" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
    findstr /l /c:"Type: http" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
    findstr /l /c:"URL: %MCP_URL%" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
    if "!MCP_MATCH!"=="1" (
        call :REPORT_CLAUDE_MCP_STATUS "%MCP_NAME%" "%MCP_URL%" "%MCP_CHECK_FILE%" "スキップ"
        del /q "%MCP_CHECK_FILE%" >nul 2>nul
        exit /b 0
    )
)
if not "!MCP_GET_STATUS!"=="0" (
    findstr /l /c:"No MCP server named" /c:"No MCP server found with name" "%MCP_CHECK_FILE%" >nul
    if not !errorlevel!==0 (
        echo       Claude Code / %MCP_NAME%: 失敗^(現在の設定を確認できませんでした^)
        type "%MCP_CHECK_FILE%"
        set /a MCP_FAILURES+=1
        del /q "%MCP_CHECK_FILE%" >nul 2>nul
        exit /b 0
    )
)
if "!MCP_GET_STATUS!"=="0" (

    echo       Claude Code / %MCP_NAME%: 古い設定を更新します
    call claude mcp remove "%MCP_NAME%"
    if not !errorlevel!==0 (
        echo       Claude Code / %MCP_NAME%: 失敗^(古い設定を削除できませんでした^)
        set /a MCP_FAILURES+=1
        del /q "%MCP_CHECK_FILE%" >nul 2>nul
        exit /b 0
    )
)

call claude mcp add --transport http --scope user "%MCP_NAME%" "%MCP_URL%"
set "MCP_ADD_STATUS=!errorlevel!"
call claude mcp get "%MCP_NAME%" >"%MCP_CHECK_FILE%" 2>&1
set "MCP_GET_STATUS=!errorlevel!"
if "!MCP_GET_STATUS!"=="0" (
    call :REPORT_CLAUDE_MCP_STATUS "%MCP_NAME%" "%MCP_URL%" "%MCP_CHECK_FILE%" "成功"
    if not !MCP_ADD_STATUS!==0 (
        echo       Claude Code / %MCP_NAME%: 失敗^(CLI終了コード !MCP_ADD_STATUS!^)
        set /a MCP_FAILURES+=1
    )
) else (
    echo       Claude Code / %MCP_NAME%: 失敗^(設定後の確認NG、CLI終了コード !MCP_ADD_STATUS!^)
    type "%MCP_CHECK_FILE%"
    set /a MCP_FAILURES+=1
)
del /q "%MCP_CHECK_FILE%" >nul 2>nul
exit /b 0

:GET_CODEX_AUTH_STATUS
set "MCP_NAME=%~1"
set "CODEX_AUTH_STATUS="
set "MCP_LIST_FILE=%TEMP%\aidd-agent-kit-mcp-list-!RANDOM!-!RANDOM!.json"
set "MCP_AUTH_FILE=%TEMP%\aidd-agent-kit-mcp-auth-!RANDOM!-!RANDOM!.txt"
call codex mcp list --json >"!MCP_LIST_FILE!" 2>&1
set "MCP_LIST_STATUS=!errorlevel!"
if not "!MCP_LIST_STATUS!"=="0" (
    type "!MCP_LIST_FILE!"
    del /q "!MCP_LIST_FILE!" "!MCP_AUTH_FILE!" >nul 2>nul
    exit /b 1
)
call node -e "let i='';process.stdin.on('data',c=^>i+=c);process.stdin.on('end',()=^>{const s=JSON.parse(i).find(x=^>x.name===process.argv[1]);if(!s^|^|typeof s.auth_status!=='string')process.exit(2);process.stdout.write(s.auth_status)})" "%MCP_NAME%" <"!MCP_LIST_FILE!" >"!MCP_AUTH_FILE!" 2>nul
set "MCP_PARSE_STATUS=!errorlevel!"
if "!MCP_PARSE_STATUS!"=="0" set /p "CODEX_AUTH_STATUS="<"!MCP_AUTH_FILE!"
del /q "!MCP_LIST_FILE!" "!MCP_AUTH_FILE!" >nul 2>nul
if not "!MCP_PARSE_STATUS!"=="0" exit /b 1
if not defined CODEX_AUTH_STATUS exit /b 1
exit /b 0

:REPORT_CODEX_MCP_STATUS
set "MCP_NAME=%~1"
call :GET_CODEX_AUTH_STATUS "%MCP_NAME%"
if not !errorlevel!==0 (
    echo       OpenAI Codex / %MCP_NAME%: 失敗^(認証状態を確認できませんでした^)
    set /a MCP_FAILURES+=1
    exit /b 0
)
if /i "!CODEX_AUTH_STATUS!"=="o_auth" (
    echo       OpenAI Codex / %MCP_NAME%: 設定済み・認証済み^(接続ready^)
    set /a MCP_REGISTERED+=1
    set /a MCP_READY+=1
    exit /b 0
)
if /i "!CODEX_AUTH_STATUS!"=="bearer_token" (
    echo       OpenAI Codex / %MCP_NAME%: 設定済み・認証済み^(接続ready^)
    set /a MCP_REGISTERED+=1
    set /a MCP_READY+=1
    exit /b 0
)
if /i "!CODEX_AUTH_STATUS!"=="not_logged_in" (
    echo       OpenAI Codex / %MCP_NAME%: 設定済み・認証待ち
    set /a MCP_REGISTERED+=1
    set /a MCP_PENDING+=1
    exit /b 0
)
if /i "!CODEX_AUTH_STATUS!"=="unsupported" (
    echo       OpenAI Codex / %MCP_NAME%: 設定済み・認証不要^(接続ready^)
    set /a MCP_REGISTERED+=1
    set /a MCP_READY+=1
    exit /b 0
)
echo       OpenAI Codex / %MCP_NAME%: 失敗^(未確認の認証状態: !CODEX_AUTH_STATUS!^)
set /a MCP_FAILURES+=1
exit /b 0

:RUN_CODEX_MCP_ADD
set "MCP_NAME=%~1"
set "MCP_URL=%~2"
rem mcp addはuser/global登録だけ。OAuthは対象capabilityを実際に使う時に
rem codex mcp loginで行い、ここでは未使用MCPの権限を求めない。
call codex mcp add "%MCP_NAME%" --url "%MCP_URL%"
set "CODEX_ADD_STATUS=!errorlevel!"
exit /b 0

:CONFIGURE_CODEX_MCP
set "MCP_NAME=%~1"
set "MCP_URL=%~2"
set "MCP_CHECK_FILE=%TEMP%\aidd-agent-kit-mcp-!RANDOM!-!RANDOM!.txt"

call codex mcp get "%MCP_NAME%" --json >"%MCP_CHECK_FILE%" 2>&1
set "MCP_GET_STATUS=!errorlevel!"
if "!MCP_GET_STATUS!"=="0" (
    set "MCP_MATCH=1"
    findstr /l /c:"streamable_http" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
    findstr /l /c:"%MCP_URL%" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
    if "!MCP_MATCH!"=="1" (
        call :REPORT_CODEX_MCP_STATUS "%MCP_NAME%"
        del /q "%MCP_CHECK_FILE%" >nul 2>nul
        exit /b 0
    )
)
if not "!MCP_GET_STATUS!"=="0" (
    findstr /l /c:"No MCP server named" /c:"No MCP server found with name" "%MCP_CHECK_FILE%" >nul
    if not !errorlevel!==0 (
        echo       OpenAI Codex / %MCP_NAME%: 失敗^(現在の設定を確認できませんでした^)
        type "%MCP_CHECK_FILE%"
        set /a MCP_FAILURES+=1
        del /q "%MCP_CHECK_FILE%" >nul 2>nul
        exit /b 0
    )
)
if "!MCP_GET_STATUS!"=="0" (

    echo       OpenAI Codex / %MCP_NAME%: 古い設定を更新します
    call codex mcp remove "%MCP_NAME%"
    if not !errorlevel!==0 (
        echo       OpenAI Codex / %MCP_NAME%: 失敗^(古い設定を削除できませんでした^)
        set /a MCP_FAILURES+=1
        del /q "%MCP_CHECK_FILE%" >nul 2>nul
        exit /b 0
    )
)

call :RUN_CODEX_MCP_ADD "%MCP_NAME%" "%MCP_URL%"
call codex mcp get "%MCP_NAME%" --json >"%MCP_CHECK_FILE%" 2>&1
set "MCP_GET_STATUS=!errorlevel!"
set "MCP_MATCH=1"
if not "!MCP_GET_STATUS!"=="0" set "MCP_MATCH=0"
findstr /l /c:"streamable_http" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
findstr /l /c:"%MCP_URL%" "%MCP_CHECK_FILE%" >nul || set "MCP_MATCH=0"
if "!MCP_MATCH!"=="1" (
    call :REPORT_CODEX_MCP_STATUS "%MCP_NAME%"
) else (
    echo       OpenAI Codex / %MCP_NAME%: 失敗^(設定後の確認NG、CLI終了コード !CODEX_ADD_STATUS!^)
    type "%MCP_CHECK_FILE%"
    set /a MCP_FAILURES+=1
)
del /q "%MCP_CHECK_FILE%" >nul 2>nul
exit /b 0

:PRECHECK_ENV
where powershell.exe >nul 2>nul
if errorlevel 1 (
    echo [エラー] Windows PowerShell が見つかりません。
    echo このセットアップは Windows 標準の PowerShell 5.1 以上を使用します。
    echo この画面のままIT担当者にお見せください。
    exit /b 1
)

rem AppLocker / WDAC / グループポリシー配下では PowerShell が ConstrainedLanguage になり、
rem pnpm のインストールスクリプトが途中で失敗する。原因を先に名指しして止める。
set "AIDD_LANG_MODE="
for /f "usebackq delims=" %%M in (`powershell -NoProfile -NonInteractive -Command "$ExecutionContext.SessionState.LanguageMode" 2^>nul`) do set "AIDD_LANG_MODE=%%M"
if not defined AIDD_LANG_MODE (
    echo [エラー] Windows PowerShell を起動できませんでした。
    echo セキュリティソフトや会社のポリシーが実行を妨げている可能性があります。
    echo この画面のままIT担当者にお見せください。
    exit /b 1
)
if /i not "%AIDD_LANG_MODE%"=="FullLanguage" (
    echo [エラー] PowerShell が制限モードで動作しています ^(%AIDD_LANG_MODE%^)。
    echo 会社のセキュリティ設定^(AppLocker / WDAC / グループポリシー^)による制限です。
    echo キット側では回避できません。この画面のままIT担当者にお見せください。
    exit /b 1
)

rem Mark of the Web の自己解除。ZIP を展開した直後は中の全ファイルに
rem 「別のコンピューターから取得したファイル」印が付く。このキットの配下だけを外す。
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath $env:AIDD_KIT_DIR -Recurse -Force -File | Unblock-File" >>"%AIDD_LOG%" 2>&1
if errorlevel 1 (
    echo [注意] キットのブロックを自動解除できませんでした。
    echo         今回のセットアップは続けますが、次回も警告が出る可能性があります。
    echo         詳しい記録: %AIDD_LOG%
    echo         手動解除: キットのフォルダで PowerShell を開き、
    echo           Get-ChildItem -Recurse -Force -File ^| Unblock-File
)
exit /b 0

:PAUSE_IF_INTERACTIVE
if not "%AIDD_NONINTERACTIVE%"=="1" pause
exit /b 0

:fail
call :RECORD_SETUP_STATE failed
echo.
if defined AIDD_LOG if exist "%AIDD_LOG%" (
    echo 詳しい記録: %AIDD_LOG%
    echo このファイルを導入支援の担当者にお送りください。
    echo.
)
call :PAUSE_IF_INTERACTIVE
exit /b 1
