#!/usr/bin/python

import argparse
import json
import math
import os
import pickle
import requests
import sys


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
    universe = requests.post('https://np.ironhelmet.com/trequest/order',
        data = {'type':'order', 'order':'full_universe_report', 'version':'', 'game_number':'5380395345117184'},
        cookies=cookies).json()
    # print("Universe: %s" % json.dumps(universe))
    with open("universe.json", "w") as f:
        f.write(json.dumps(universe))
    return universe


def player_stars(universe, player_id):
    stars = []
    for id, star in universe['report']['stars'].items():
        if star['puid'] == player_id:
            stars.append(star)
    return sorted(stars, key = lambda i: i['n'])

'''
    universe.calcUCE = function (star) {
        if (star.player !== universe.player) return 0;
        let e = star.e + 1;
        return Math.floor((10 * e * e) / (star.r / 100));
    };
    universe.calcUCI = function (star) {
        if (star.player !== universe.player) return 0;
        let i = star.i + 1;
        return Math.floor((15 * i * i) / (star.r / 100));
    };
    universe.calcUCS = function (star) {
        if (star.player !== universe.player) return 0;
        let s = star.s + 1;
        return Math.floor((20 * s * s) / (star.r / 100));
    };
'''
def star_upgrade_costs(star):
    e = star['e'] + 1
    i = star['i'] + 1
    s = star['s'] + 1
    return {
        'economy': math.floor((10.0 * e * e) / (star['r'] / 100.0)),
        'industry': math.floor((15.0 * i * i) / (star['r'] / 100.0)),
        'science': math.floor((20.0 * s * s) / (star['r'] / 100.0)),
    }


def star_upgrades(stars):
    for star in stars:
        upgrades = star_upgrade_costs(star)
        print("%s: e:%d i:%d s:%d" % (star['n'], upgrades["economy"], upgrades["industry"], upgrades["science"]))


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


if __name__ == '__main__':
    main()