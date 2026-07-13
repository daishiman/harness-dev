"""coverage.py の subprocess 計測フック。

tests が subprocess.run([sys.executable, script]) で起動する CLI スクリプトの行カバレッジを
回収するため、COVERAGE_PROCESS_START が設定されていれば子プロセス起動時に coverage を開始する。
リポジトリルートを PYTHONPATH に含めて実行することで Python がこのモジュールを自動 import する。
"""
import os

if os.environ.get("COVERAGE_PROCESS_START"):
    try:
        import coverage

        coverage.process_startup()
    except Exception:
        pass
