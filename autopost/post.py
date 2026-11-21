# -*- coding: utf-8 -*-
"""Instagram Reels auto-poster (official Instagram Graph API, resumable upload).

Modes:
  decide          -> works out if a reel is due right now; writes `folder` and `slot` to $GITHUB_OUTPUT
  post            -> uploads + publishes one reel (--folder, --slot) and records it in posted.json
  check           -> verifies the token and prints the Instagram username (posts nothing)

Secrets (GitHub Actions env): IG_ACCESS_TOKEN, IG_USER_ID
"""
import argparse, datetime as dt, json, os, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
CFG = json.loads((HERE / 'config.json').read_text(encoding='utf-8'))
LOG_PATH = HERE / 'posted.json'
GRAPH = f"https://graph.facebook.com/{CFG['graph_version']}"
RUPLOAD = f"https://rupload.facebook.com/ig-api-upload/{CFG['graph_version']}"
TZ = dt.timezone(dt.timedelta(hours=5, minutes=30))  # India (IST)


def load_log():
    return json.loads(LOG_PATH.read_text(encoding='utf-8')) if LOG_PATH.exists() else {'posted': []}


def save_log(log):
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def queue(name='queue.txt'):
    items = [l.strip() for l in (HERE / name).read_text(encoding='utf-8').splitlines() if l.strip()]
    return [i for i in items if i not in CFG.get('skip', [])]


def next_reel(log, name='queue.txt'):
    done = {p['reel'] for p in log['posted']}
    return next((r for r in queue(name) if r not in done), None)


def slots_on(day, slots=None):
    kind = 'weekend' if day.weekday() >= 5 else 'weekday'
    out = []
    for hhmm in (slots or CFG['slots'])[kind]:
        h, m = map(int, hhmm.split(':'))
        out.append(dt.datetime(day.year, day.month, day.day, h, m, tzinfo=TZ))
    return out


def due_slot(now, log, slots=None, start_date=None):
    """Return the slot (datetime) that is due now and not yet used, else None."""
    start = dt.date.fromisoformat(start_date or CFG['start_date'])
    used = {p['slot'] for p in log['posted']}
    window = dt.timedelta(minutes=CFG['window_minutes'])
    for day in (now.date() - dt.timedelta(days=1), now.date()):
        if day < start:
            continue
        for s in slots_on(day, slots):
            key = s.strftime('%Y-%m-%dT%H:%M')
            if s <= now < s + window and key not in used:
                return key
    return None


def caption_for(folder):
    text = (ROOT / 'reels' / folder / 'caption.txt').read_text(encoding='utf-8')
    return text.split('\n---\n')[0].strip()


def write_output(**kv):
    out = os.environ.get('GITHUB_OUTPUT')
    for k, v in kv.items():
        print(f'{k}={v}')
        if out:
            with open(out, 'a', encoding='utf-8') as f:
                f.write(f'{k}={v}\n')


# ---------------- Instagram API ----------------
def api(method, url, **kw):
    import requests
    r = requests.request(method, url, timeout=120, **kw)
    try:
        data = r.json()
    except ValueError:
        data = {'raw': r.text[:500]}
    if r.status_code >= 400 or 'error' in data:
        raise SystemExit(f'Instagram API error ({r.status_code}) on {url.split("?")[0]}: {json.dumps(data, ensure_ascii=False)[:800]}')
    return data


def creds():
    tok, uid = os.environ.get('IG_ACCESS_TOKEN'), os.environ.get('IG_USER_ID')
    if not tok or not uid:
        raise SystemExit('IG_ACCESS_TOKEN / IG_USER_ID secrets missing. Guide ka Step 6 dekho.')
    return tok, uid


def check():
    tok, uid = creds()
    me = api('GET', f'{GRAPH}/{uid}', params={'fields': 'username,media_count', 'access_token': tok})
    print(f"OK: token sahi hai. Instagram account: @{me.get('username')} ({me.get('media_count')} posts)")
    log = load_log()
    print(f"Agli reel queue mein: {next_reel(log)}")


def try_upload_curl(url, video, tok, size):
    """Exactly the curl command from Meta's docs. Token goes via a temp header file, not argv."""
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.h') as h:
        h.write(f'Authorization: OAuth {tok}\noffset: 0\nfile_size: {size}\n')
        hpath = h.name
    try:
        r = subprocess.run(['curl', '-sS', '-X', 'POST', url, '-H', f'@{hpath}', '--data-binary', f'@{video}', '-w', '\nHTTP %{http_code}'],
                           capture_output=True, text=True, timeout=600)
    finally:
        os.unlink(hpath)
    out = (r.stdout + r.stderr).strip()
    code = out.rsplit('HTTP ', 1)[-1].strip() if 'HTTP ' in out else '000'
    body = out.rsplit('\nHTTP ', 1)[0][:400]
    ok = code.startswith('2') and '"success":true' in body.replace(' ', '')
    return ok, f'curl HTTP {code}: {body}'


def try_upload(url, data, tok, size, extra):
    """POST raw video bytes to the rupload endpoint. Returns (ok, short_response)."""
    import requests
    headers = {'Authorization': f'OAuth {tok}', 'offset': '0', 'file_size': str(size)}
    headers.update(extra)
    try:
        r = requests.post(url, data=data, headers=headers, timeout=300)
    except Exception as e:  # network error
        return False, f'network error: {e}'
    text = r.text[:400]
    ok = r.status_code < 400 and '"error"' not in text and 'debug_info' not in text
    return ok, f'HTTP {r.status_code}: {text}'


def create_from_url(folder, cap, tok, uid):
    """video_url method: Instagram downloads the reel from a public link (repo must be public)."""
    import requests
    url = CFG['video_base_url'].rstrip('/') + f'/{folder}/reel.mp4'
    h = requests.head(url, allow_redirects=True, timeout=60)
    print(f'video link: {url} -> HTTP {h.status_code}, {h.headers.get("Content-Type")}, {h.headers.get("Content-Length")} bytes')
    if h.status_code != 200:
        raise SystemExit('Video ka public link nahi khul raha. Kya GitHub repo Public hai? (Settings -> General -> Change visibility)')
    c = api('POST', f'{GRAPH}/{uid}/media', data={
        'media_type': 'REELS', 'video_url': url, 'caption': cap, 'share_to_feed': 'true',
        'thumb_offset': str(CFG.get('thumb_offset_ms', 1500)), 'access_token': tok})
    print('container', c['id'])
    return c['id']


def post(folder, slot, publish=True):
    tok, uid = creds()
    video = ROOT / 'reels' / folder / 'reel.mp4'
    size = video.stat().st_size
    cap = caption_for(folder)
    print(f'Posting {folder} ({size / 1e6:.1f} MB) for slot {slot}  [API {CFG["graph_version"]}]')
    if CFG.get('video_base_url'):
        cid = create_from_url(folder, cap, tok, uid)
        return finish(cid, tok, uid, folder, slot, publish)
    data = video.read_bytes()

    # 1+2. create a resumable REELS container and upload the bytes.
    # Only the parameters the docs allow for resumable uploads are sent (no share_to_feed).
    # Tried with the Page token first, then with the optional User token (IG_USER_TOKEN secret).
    tokens = [('page-token', tok)]
    utok = os.environ.get('IG_USER_TOKEN')
    if utok:
        tokens.append(('user-token', utok))
    cid = None
    attempts = [(n, t, 'curl') for n, t in tokens] + [(n, t, 'requests') for n, t in tokens]
    for name, t, how in attempts:
        c = api('POST', f'{GRAPH}/{uid}/media', data={
            'media_type': 'REELS', 'upload_type': 'resumable', 'caption': cap,
            'thumb_offset': str(CFG.get('thumb_offset_ms', 1500)), 'access_token': t})
        cand = c['id']
        url = c.get('uri') or f'{RUPLOAD}/{cand}'
        print(f'container {cand} | upload try "{name}/{how}" -> {url.split("?")[0]}')
        if how == 'curl':
            ok, resp = try_upload_curl(url, video, t, size)
        else:
            ok, resp = try_upload(url, data, t, size, {})
        print('   ', resp)
        if ok:
            cid, tok = cand, t
            break
        st = api('GET', f'{GRAPH}/{cand}', params={'fields': 'status_code,status,video_status', 'access_token': t})
        print('    container status after failed upload:', json.dumps(st, ensure_ascii=False)[:600])
    if not cid:
        hint = '' if utok else ' (Tip: IG_USER_TOKEN secret bhi daalo, guide dekho.)'
        raise SystemExit('Video upload fail hua. Upar ke logs mujhe bhejo.' + hint)
    print('uploaded')
    return finish(cid, tok, uid, folder, slot, publish)


def finish(cid, tok, uid, folder, slot, publish):
    # 3. wait for Instagram to process the video
    for _ in range(60):
        st = api('GET', f'{GRAPH}/{cid}', params={'fields': 'status_code,status', 'access_token': tok})
        code = st.get('status_code')
        print('status', code, '-', st.get('status', ''))
        if code == 'FINISHED':
            break
        if code in ('ERROR', 'EXPIRED'):
            raise SystemExit(f'Instagram ne video reject kiya: {st}')
        time.sleep(10)
    else:
        raise SystemExit('Video processing 10 minute mein poori nahi hui')

    if not publish:
        print('TEST OK: video upload aur processing dono sahi. (test mode, kuch publish nahi kiya)')
        return

    # 4. publish
    pub = api('POST', f'{GRAPH}/{uid}/media_publish', data={'creation_id': cid, 'access_token': tok})
    mid = pub['id']
    link = api('GET', f'{GRAPH}/{mid}', params={'fields': 'permalink', 'access_token': tok}).get('permalink', '')
    print('PUBLISHED', mid, link)

    log = load_log()
    log['posted'].append({'slot': slot, 'reel': folder, 'media_id': mid, 'permalink': link,
                          'posted_at': dt.datetime.now(TZ).strftime('%Y-%m-%d %H:%M IST')})
    save_log(log)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['decide', 'post', 'check', 'test-upload'])
    ap.add_argument('--folder')
    ap.add_argument('--slot')
    ap.add_argument('--force', action='store_true', help='decide: ignore schedule, pick next reel now')
    ap.add_argument('--now', help='testing only: pretend current IST time, e.g. 2026-11-20T13:10')
    a = ap.parse_args()

    if a.mode == 'check':
        return check()
    if a.mode == 'post':
        return post(a.folder, a.slot)
    if a.mode == 'test-upload':
        return post(a.folder, 'test', publish=False)

    log = load_log()
    now = dt.datetime.fromisoformat(a.now).replace(tzinfo=TZ) if a.now else dt.datetime.now(TZ)
    slot = due_slot(now, log)
    if a.force and not slot:  # manual run outside a slot window
        slot = 'manual-' + now.strftime('%Y-%m-%dT%H:%M')
    reel = next_reel(log) if slot else None
    if not reel and not a.force:  # extra series with their own queue + time slots (e.g. funny clay reels at 5 PM)
        for name, ser in CFG.get('series', {}).items():
            s2 = due_slot(now, log, ser['slots'], ser['start_date'])
            r2 = next_reel(log, ser['queue']) if s2 else None
            if r2:
                print(f'series "{name}": slot {s2}')
                slot, reel = s2, r2
                break
    if not slot:
        print(f'{now:%Y-%m-%d %H:%M} IST: abhi koi post due nahi hai.')
        return write_output(folder='', slot='')
    if not reel:
        print('Queue khatam! Saari reels post ho chuki hain. Nayi reels queue.txt mein jodo.')
        return write_output(folder='', slot='')
    write_output(folder=reel, slot=slot)


if __name__ == '__main__':
    main()
