"""The manager page in a real Edge, against a fake GitHub API (nothing leaves the machine).

    python manage/e2e_test.py        (needs playwright; the billing-gateway venv of the private repo has it)
"""
import base64
import functools
import http.server
import json
from pathlib import Path
import re
import sys
import threading

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
failures = []


def check(name, condition, detail=''):
    print(('PASS  ' if condition else 'FAIL  ') + name + ('' if condition else f'  -> {detail}'))
    if not condition: failures.append(name)


class FakeGitHub:
    """Contents API of two repositories, in memory."""
    def __init__(self): self.files, self.puts = {}, []

    def handle(self, route):
        request = route.request
        match = re.match(r'https://api\.github\.com/repos/([^/]+/[^/]+)/contents/(.+)$', request.url)
        if request.headers.get('authorization') != 'Bearer test-token': return route.fulfill(status=401, body='{"message":"Bad credentials"}')
        key = (match[1], match[2])
        if request.method == 'GET':
            if key not in self.files: return route.fulfill(status=404, body='{"message":"Not Found"}')
            text, sha = self.files[key]
            return route.fulfill(status=200, content_type='application/json', body=json.dumps({'content': base64.b64encode(text.encode()).decode(), 'sha': sha}))
        body = json.loads(request.post_data)
        if key in self.files and body.get('sha') != self.files[key][1]: return route.fulfill(status=409, body='{"message":"sha mismatch"}')
        text = base64.b64decode(body['content']).decode()
        sha = f'sha{len(self.puts) + 1}'
        self.files[key] = (text, sha); self.puts.append((key, text))
        return route.fulfill(status=200, content_type='application/json', body=json.dumps({'content': {'sha': sha}}))

    def json(self, repo, path): return json.loads(self.files[(repo, path)][0])


def main():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *_): pass
    handler = functools.partial(Quiet, directory=str(HERE))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/index.html'
    github = FakeGitHub()
    answers, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page()
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.on('dialog', lambda d: d.accept(answers.pop(0) if answers and d.type == 'prompt' else None) if d.type == 'prompt' else d.accept())
        page.route('https://api.github.com/**', github.handle)
        page.add_init_script("localStorage.setItem('paid.token','test-token')")
        page.goto(url); page.wait_for_selector('text=Chưa có khách nào')
        check('an empty list on first use', 'Chưa xuất bản lần nào' in page.inner_text('body'))

        answers[:] = ['Nguyễn A', 'zalo 0900', '3FA9-1C2B-7D10-4E5A', '0', 'PC nhà']
        page.click('#addCustomer'); page.wait_for_selector('text=3fa9-1c2b-7d10-4e5a')
        check('adding a device asks to publish', not page.is_disabled('#publish') and 'chưa xuất bản' in page.inner_text('#pending'))
        page.fill('#message', 'Chuyển khoản ngày 15, liên hệ 0900')
        page.click('#publish'); page.wait_for_selector('text=Đã xuất bản serial 1')
        status = github.json('ArsNeonci/audio-endpoint', 'status.json')
        customers = github.json('ArsNeonci/licence-hub', 'customers.json')
        check('the public file has the code, a date and the message', status['serial'] == 1 and list(status['devices']) == ['3fa91c2b7d104e5a'] and status['message'].startswith('Chuyển khoản'), status)
        check('the public file names nobody', 'Nguyễn' not in json.dumps(status, ensure_ascii=False) and 'zalo' not in json.dumps(status), status)
        check('the private file keeps the customer', customers['customers'][0]['name'] == 'Nguyễn A' and customers['customers'][0]['contact'] == 'zalo 0900')
        first = status['devices']['3fa91c2b7d104e5a']
        check('a paid new device runs to 23:59:59 Vietnam time on the 16th', first.endswith('T16:59:59Z') and first[8:10] in ('16',), first)

        page.reload(); page.wait_for_selector('text=3fa9-1c2b-7d10-4e5a')
        check('a reload shows what is live', 'serial 1' in page.inner_text('#published'))
        page.check('.pick'); page.click('[data-extend="1"]'); page.click('#publish'); page.wait_for_selector('text=Đã xuất bản serial 2')
        second = github.json('ArsNeonci/audio-endpoint', 'status.json')['devices']['3fa91c2b7d104e5a']
        check('extending one month moves the date one month on', second > first and second.endswith('T16:59:59Z'), (first, second))

        page.check('.pick'); page.click('#lockPicked'); page.wait_for_selector('text=ĐÃ KHOÁ')
        page.click('#publish'); page.wait_for_selector('text=Đã xuất bản serial 3')
        locked = github.json('ArsNeonci/audio-endpoint', 'status.json')['devices']['3fa91c2b7d104e5a']
        check('locking now puts the date in the past', locked < first, locked)
        page.click('[data-open]'); page.click('#publish'); page.wait_for_selector('text=Đã xuất bản serial 4')
        opened = github.json('ArsNeonci/audio-endpoint', 'status.json')['devices']['3fa91c2b7d104e5a']
        check('unlocking opens it until the next lock day', opened > locked and opened.endswith('T16:59:59Z'), opened)

        answers[:] = ['Trần B', '', 'not-a-code']
        page.click('#addCustomer')
        check('a wrong device code is refused', len(github.json('ArsNeonci/licence-hub', 'customers.json')['customers']) == 1)
        # Someone else published meanwhile: the page reads the live serial again instead of going back.
        live = github.json('ArsNeonci/audio-endpoint', 'status.json'); live['serial'] = 40
        github.files[('ArsNeonci/audio-endpoint', 'status.json')] = (json.dumps(live), 'sha-other')
        page.click('#extendAll'); page.click('#publish'); page.wait_for_selector('text=Đã xuất bản serial 41')
        check('a newer live serial is never gone back on', github.json('ArsNeonci/audio-endpoint', 'status.json')['serial'] == 41)
        unexpected = [e for e in errors if 'status of 404' not in e]   # first use: no files yet (and no favicon) is expected
        check('no errors in the page', not unexpected, unexpected[:3])
        browser.close()
    server.shutdown()
    print(f'\n{len(failures)} failed')
    sys.exit(1 if failures else 0)


if __name__ == '__main__': main()
