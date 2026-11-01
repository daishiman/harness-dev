"""検査済みの配布物を、指定済みの既存資料へ差分だけ反映する。"""
import hashlib
import json
import os
import tempfile
from pathlib import Path

WORK = Path(__file__).resolve().parent
source_info = json.loads((WORK / 'source.json').read_text())
target = Path(source_info['source_dir'])
backup = Path(source_info['backup_dir'])
stage = Path(json.loads((WORK / 'final-stage.json').read_text())['path'])
report = json.loads((stage / '改善レポート.json').read_text())
review = report['独立読みやすさレビュー']
assert review['status'] == 'ok' and review['verdict'] == 'PASS'
assert not any(x.get('reason_code') == 'display_unavailable' for x in review['not_reviewed'])
assert report['静的ゲート']['verdict'] == 'pass'
assert report['再現性']['HTMLバイト一致']
expected = report['再現性']['HTML_SHA256']
assert hashlib.sha256((stage / 'handout.html').read_bytes()).hexdigest() == expected
assert report['静的ゲート']['html_sha256'] == expected
assert json.loads((WORK / 'visual-evidence.json').read_text())['html_sha256'] == expected
for name in ['handout.html', 'handout-config.json', 'README.md', '.handout-route.json']:
    assert (target / name).read_bytes() == (backup / name).read_bytes(), f'元ファイルが作業中に変更された: {name}'
names = ['handout-config.json', 'handout-config.json.visual-selection.json', 'README.md',
         '.handout-route.json', '改善レポート.json', 'assets/images/qr-speaker-links-readable.svg', 'handout.html']
prepared = []
try:
    for name in names:
        destination = target / name
        data = (stage / name).read_bytes()
        handle, temp_name = tempfile.mkstemp(prefix='.handout-update-', dir=destination.parent)
        with os.fdopen(handle, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, destination.stat().st_mode & 0o777 if destination.exists() else 0o644)
        prepared.append((temp_name, destination, data))
    for temp_name, destination, data in prepared:
        os.replace(temp_name, destination)
        assert destination.read_bytes() == data
finally:
    for temp_name, _, _ in prepared:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
assert hashlib.sha256((target / 'handout.html').read_bytes()).hexdigest() == expected
(WORK / 'placement.json').write_text(json.dumps({'target': str(target), 'html_sha256': expected,
    'files': names, 'backup': str(backup)}, ensure_ascii=False, indent=2) + '\n')
print('反映完了:', target / 'handout.html')
print('変更ファイル数:', len(names), 'HTML SHA256:', expected)
