"""
Fetch KeepTradeCut dynasty values and write ktc.csv.

Adapted from ees4/KeepTradeCut-Scraper, trimmed to the one job this needs:
superflex and 1QB values for every player, straight to a CSV that the game can
read. No Google Sheets, no credentials.
"""
import csv, time, sys
import requests
from bs4 import BeautifulSoup

# RDP is KTC's code for rookie draft picks. They are ranked alongside players
# and carry real trade value, so they are wanted here -- a trade of picks for a
# player cannot be graded without them.
URL = "https://keeptradecut.com/dynasty-rankings?page={0}&filters=QB|WR|RB|TE|RDP&format={1}"
PAGES = 10                     # KTC pages 0-9 covers the full ranked list


def scrape(fmt):
    """fmt: 1 = one-quarterback, 0 = superflex. Returns {name: (pos, team, rookie, value)}."""
    out = {}
    for page in range(PAGES):
        r = requests.get(URL.format(page, fmt), timeout=30,
                         headers={'User-Agent': 'Mozilla/5.0 (ktc-updater)'})
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'html.parser')
        for el in soup.find_all(class_='onePlayer'):
            name_el = el.find(class_='player-name')
            pos_el = el.find(class_='position')
            val_el = el.find(class_='value')
            if not (name_el and pos_el and val_el):
                continue
            raw = name_el.get_text(strip=True)

            # KTC appends the team to the name, and prefixes rookies with R:
            # "Ja'Marr ChaseCIN", "Jeremiyah LoveRARI". Peel that off.
            suffix = ''
            for n in (4, 3, 2):
                tail = raw[-n:]
                if tail == 'RFA' or (n == 4 and raw[-4] == 'R' and tail[1:].isupper()) \
                   or tail == 'FA' or (n == 3 and tail.isupper()):
                    suffix = tail
                    break
            name = raw[:len(raw) - len(suffix)].strip() if suffix else raw
            rookie = suffix.startswith('R') and len(suffix) == 4
            team = suffix[1:] if rookie else suffix

            pos_rank = pos_el.get_text(strip=True)
            pos = pos_rank[:2]
            # PI is a draft pick. Keep it: its value is what makes a
            # picks-for-player trade gradeable. The name carries the detail,
            # e.g. "2026 Early 1st", "2027 Mid 2nd".
            if pos == 'PI':
                team = 'PICK'
            try:
                value = int(val_el.get_text(strip=True))
            except ValueError:
                continue
            out[name] = (pos, team or 'FA', 'Yes' if rookie else 'No', value)
        time.sleep(0.6)                          # be polite to their server
    return out


def main():
    print('fetching superflex...', flush=True)
    sf = scrape(0)
    print('fetching 1QB...', flush=True)
    oneqb = scrape(1)
    if not sf:
        sys.exit('no players found -- KTC has probably changed their markup')

    rows = []
    for name, (pos, team, rookie, sfval) in sf.items():
        rows.append({
            'Player Name': name,
            'Position': pos,
            'Team': team,
            'Rookie': rookie,
            'SFValue': sfval,
            'Value': oneqb.get(name, (None, None, None, 0))[3],
        })
    rows.sort(key=lambda r: -r['SFValue'])

    with open('ktc.csv', 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['Player Name', 'Position', 'Team',
                                           'Rookie', 'SFValue', 'Value'])
        w.writeheader()
        w.writerows(rows)
    print('wrote ktc.csv with %d players' % len(rows))
    print('top 5: ' + ', '.join('%s %d' % (r['Player Name'], r['SFValue']) for r in rows[:5]))


if __name__ == '__main__':
    main()
