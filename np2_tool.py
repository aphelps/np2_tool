#!/usr/bin/python

import argparse
import json
import math
import os
import pickle
import requests
import sys

################################################################################
# Constants
#

# 3 hours per LY
LIGHT_YEAR_TIME = 3

# 1 star scale = 8 light years observed
# docs say 1/16, but seem to be wrong
LIGHT_YEAR_SCALE = 8


def handle_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("-l", "--login", help="Login ID")
    parser.add_argument("-p", "--password", help="password")
    parser.add_argument("-C", "--credentials", default="creds.np", help="Cookies output file [default: %(default)s]")
    parser.add_argument("-g", "--gameid", type=int, default=5380395345117184, help="Game ID")

    parser.add_argument("-v", "--verbose", action="store_true")

    options = parser.parse_args()

    if (not os.path.isfile(options.credentials)) and (options.login is None or options.password is None):
        print("Must provide cookes file or login/password")
        sys.exit(1)

    return options


def load_cookies(login, password, credentials):
    cookies = None
    if login:
        print("Logging in with email/password")
        cookies = requests.post('https://np.ironhelmet.com/arequest/login',
                                data={'type': 'login',
                                      'alias': login,
                                      'password': password}).cookies
        # print("Cookies: %s" % cookies)

        if credentials:
            with open(credentials, "wb") as creds:
                pickle.dump(cookies, creds)
                print("Wrote cookies to %s" % credentials)
    else:
        # Read the cookies from a file
        with open(credentials, 'rb') as creds:
            cookies = pickle.load(creds)
            print("Read cookies from %s" % credentials)

    return cookies


def get_universe(cookies, game_id):
    response = requests.post('https://np.ironhelmet.com/trequest/order',
                             data={'type':'order',
                                   'order':'full_universe_report',
                                   'version':'',
                                   'game_number':'5380395345117184'},
                             cookies=cookies)
    # print("Universe: %s" % json.dumps(universe))

    universe = response.json()
    if response.status_code != requests.codes.ok:
        print("get_universe(): request failed, code %d" % response.status_code)
        print("  data: %s" % response.text)
        sys.exit(1)

    if 'player_uid' not in universe['report']:
        print("get_universe(): invalid universe: %s" % (json.dumps(universe)))
        sys.exit()

    with open("universe.json", "w") as f:
        f.write(json.dumps(universe))
    return universe


def player_stars(universe, player_id):
    stars = []
    for id, star in universe['report']['stars'].items():
        if star['puid'] == player_id:
            stars.append(star)
    return sorted(stars, key = lambda i: i['n'])


# Star format:
#     {
#         u'e': 4,             # Economy
#         u'uid': 294,         # Star ID
#         u'i': 3,             # Industry
#         u'puid': 5,          # Player ID
#         u'n': u'Sham',       # Name
#         u's': 2,             # Science
#         u'r': 40,            # Resources
#         u'exp': 0,
#         u'v': u'1',
#         u'y': u'5.04934006', # y location
#         u'x': u'0.69888656', # x location
#         u'ga': 0,
#         u'st': 290           # Ships
#     }

def star_upgrade_costs(star):
    e = star['e'] + 1
    i = star['i'] + 1
    s = star['s'] + 1
    return {
        'economy': math.floor((10.0 * e * e) / (star['r'] / 100.0)),
        'industry': math.floor((15.0 * i * i) / (star['r'] / 100.0)),
        'science': math.floor((20.0 * s * s) / (star['r'] / 100.0)),
    }


def star_by_name(stars, name):
    return next(star for star in stars if star["n"] == name)


def star_by_id(stars, id):
    return next(star for star in stars if star["uid"] == id)


def star_upgrades(stars):
    for star in stars:
        upgrades = star_upgrade_costs(star)
        print("%s[%s]: e:%d i:%d s:%d" % (star['n'], star['uid'], upgrades["economy"], upgrades["industry"], upgrades["science"]))


def star_distance(star1, star2):
    distance = math.sqrt(
        (float(star1['x']) - float(star2['x']))**2 +
        (float(star1['y']) - float(star2['y']))**2)
    return {
        'distance': distance * LIGHT_YEAR_SCALE,
        'time': math.ceil(distance * LIGHT_YEAR_SCALE * LIGHT_YEAR_TIME)
    }


def star_upgrade(cookies, game_id, star, type):
    id = star['uid']
    amount = star_upgrade_costs(star)['industry']
    data = {'type': 'batched_orders',
            'order': 'upgrade_%s,%d,%d' % (type, id, amount),
            'version': '',
            'game_number': '%d' % game_id}
    print("TEST: %s" % data)

    result = requests.post('https://np.ironhelmet.com/prequest/batched_orders',
                           data=data,
                           cookies=cookies)
    print('test_upgrade(): status=%d text=%s' % (result.status_code, result.text))


def main():
    options = handle_args()

    cookies = load_cookies(options.login, options.password, options.credentials)
    universe = get_universe(cookies, options.gameid)

    player_id = universe['report']['player_uid']
    player_name = universe['report']['players'][str(player_id)]['alias']
    print("Player ID: %d" % player_id)
    print("Cash: %d" % universe['report']['players'][str(player_id)]['cash'])

    stars = player_stars(universe, player_id)
    print("Player %s: %d stars" % (player_name, len(stars)))

    star_upgrades(stars)

    # test_upgrade(cookies, options.gameid, star_by_name(stars, "Kochab"), "industry")

    print('distance: %s' % star_distance(star_by_name(stars, "Alnilam"), star_by_name(stars, "Septen")))

if __name__ == '__main__':
    main()